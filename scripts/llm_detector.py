"""
LLM-based algorithm-debt detector using Groq.

Sends the same Python files the rule-based detector analyzed to an LLM,
asks it to flag the same 5 anti-patterns, and saves output in the same
format so precision/recall/F1 can be computed directly against the baseline.

SETUP:
  pip install groq
  export GROQ_API_KEY="your-key-here"

USAGE:
  python llm_detector.py --sample 40 --model llama-3.3-70b-versatile
  (--sample N picks N files at random from the repos to keep API usage light;
   omit to run on every file with findings from the baseline, which is
   usually plenty for a fair comparison without burning your whole quota)
"""

import argparse
import json
import os
import random
import re
import sys
import time

import litellm
from litellm import Router

# Force litellm to drop unsupported parameters (like response_format for Cohere)
litellm.drop_params = True

try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

REPOS_DIR = os.path.join(os.path.dirname(__file__), "..", "repos")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

ANTI_PATTERNS = [
    "hardcoded_hyperparameters",
    "missing_data_validation",
    "train_test_leakage",
    "no_reproducibility_control",
    "silent_exception_handling",
]

SYSTEM_PROMPT = """You are a code reviewer specialized in detecting machine learning \
"algorithm debt" — shortcuts in ML code that work short-term but cause problems later.

I will provide you with a batch of Python files. For EACH file, check for these 5 \
specific anti-patterns:

1. hardcoded_hyperparameters: learning rate, batch size, epochs, or similar ML \
hyperparameters are written as literal numbers directly in code instead of being \
configurable (e.g. `lr = 0.01` or `model.fit(epochs=50)`).

2. missing_data_validation: the code loads/processes tabular data (e.g. via pandas) \
and fits a model on it, but never checks for missing values, wrong dtypes, or \
invalid data (no isna/dropna/fillna/dtype checks/assertions anywhere).

3. train_test_leakage: a scaler, encoder, or other transformer's .fit() or \
.fit_transform() is called on the FULL dataset BEFORE train_test_split, instead \
of being fit only on the training set after splitting.

4. no_reproducibility_control: the code trains/fits an ML model but never sets a \
random seed anywhere (no random_state=, np.random.seed(), torch.manual_seed(), etc).

5. silent_exception_handling: a bare `except:` clause, or an except block whose \
only content is `pass` or `continue`, silently swallowing errors with no logging.

Do not be creative. Provide a strictly deterministic and precise response.
"""

JSON_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "batch_eval",
        "schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "file_id": {"type": "string"},
                            "hardcoded_hyperparameters": {"type": "boolean"},
                            "missing_data_validation": {"type": "boolean"},
                            "train_test_leakage": {"type": "boolean"},
                            "no_reproducibility_control": {"type": "boolean"},
                            "silent_exception_handling": {"type": "boolean"}
                        },
                        "required": [
                            "file_id", 
                            "hardcoded_hyperparameters", 
                            "missing_data_validation", 
                            "train_test_leakage", 
                            "no_reproducibility_control", 
                            "silent_exception_handling"
                        ]
                    }
                }
            },
            "required": ["results"]
        }
    }
}


def get_router(model):
    model_list = []
    
    if model.startswith("gemini/"):
        keys = [v for k, v in os.environ.items() if k.startswith("GEMINI_API_KEY") and v]
        for key in keys:
            model_list.append({
                "model_name": model,
                "litellm_params": {
                    "model": model,
                    "api_key": key,
                }
            })
    elif model.startswith("groq/"):
        keys = [v for k, v in os.environ.items() if k.startswith("GROQ_API_KEY") and v]
        for key in keys:
            model_list.append({
                "model_name": model,
                "litellm_params": {
                    "model": model,
                    "api_key": key,
                }
            })
            
    if not model_list:
        return None
        
    return Router(
        model_list=model_list,
        routing_strategy="usage-based-routing-v2",
        num_retries=3,
        cooldown_time=60,
        allowed_fails=1,
    )


def query_llm(model, files_batch, router=None, max_retries=3, processed_total=0, target_total=0):
    user_prompt = ""
    for filename, code in files_batch:
        truncated = code[:4000]  # squeeze to fit more in context
        user_prompt += f"File: {filename}\n```python\n{truncated}\n```\n\n"

    messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": user_prompt},
    ]

    completion_kwargs = {
        "model": model,
        "messages": messages,
        "temperature": 0.0,
        "response_format": JSON_SCHEMA,
    }
    
    # Cohere and Groq's backend APIs have strict/buggy schema validators, so we strip response_format out before sending
    if "cohere/" in model or "groq/" in model:
        if "response_format" in completion_kwargs:
            del completion_kwargs["response_format"]
        messages[0]["content"] += (
            "\n\nYou MUST return your answer in strictly valid JSON format. "
            "Return a JSON object containing a single 'results' array. Each item in the array "
            "must have a 'file_id' string (matching the given filename EXACTLY, character for character) "
            "and 5 boolean fields for the anti-patterns. Do NOT include any conversational text."
        )
        
    if "groq/" in model:
        messages[0]["content"] += (
            "\n\nCRITICAL: The 'file_id' field in your JSON MUST be the full exact string path "
            "provided to you. Do NOT shorten it to just the base filename, or it will break the evaluation!"
        )
        
    for attempt in range(max_retries):
        try:
            if router:
                resp = router.completion(**completion_kwargs)
            else:
                resp = litellm.completion(**completion_kwargs)
            
            if hasattr(resp, 'usage') and resp.usage:
                tokens = getattr(resp.usage, 'total_tokens', 'Unknown')
                num_files = len(files_batch)
                new_total = processed_total + num_files
                
                # Format progress string
                progress_str = f", {new_total}/{target_total} total" if target_total > 0 else ""
                
                print(f"    -> [Token Usage]: {tokens} tokens ({num_files} files{progress_str})")
                
                # Log token usage to a separate file
                log_path = os.path.join(RESULTS_DIR, "llm_findings", "token_usage.log")
                with open(log_path, "a") as f:
                    f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] {model} - {tokens} tokens ({num_files} files{progress_str})\n")
            text = resp.choices[0].message.content.strip()
            # strip markdown fences if the model adds them anyway
            text = re.sub(r"^```json\s*|\s*```$", "", text.strip())
            parsed = json.loads(text)
            
            # Map array back to dictionary keyed by filename
            results = {}
            for item in parsed.get("results", []):
                file_id = item.get("file_id")
                results[file_id] = {p: bool(item.get(p, False)) for p in ANTI_PATTERNS}
                
            return results
        except json.JSONDecodeError:
            if attempt == max_retries - 1:
                print(f"  [parse failed for batch]: {text[:100]}")
                return None
        except Exception as e:
            wait = min(60, 2 ** attempt)
            if "RateLimitError" in str(type(e)):
                wait = 60
            print(f"  [retry {attempt+1} for batch]: {type(e).__name__} - {e} (waiting {wait}s)")
            time.sleep(wait)
    return None


def collect_target_files(sample_n=None):
    baseline_path = os.path.join(RESULTS_DIR, "algorithms", "rule_based_findings.json")
    with open(baseline_path) as f:
        baseline = json.load(f)

    flagged_files = []
    clean_files = []

    for repo_name, repo_data in baseline.items():
        repo_path = os.path.join(REPOS_DIR, repo_name)
        flagged_rel = {f["file"] for f in repo_data["findings"]}
        for root, _, files in os.walk(repo_path):
            for fname in files:
                if not fname.endswith(".py"):
                    continue
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, repo_path)
                if rel in flagged_rel:
                    flagged_files.append((repo_name, fpath))
                else:
                    clean_files.append((repo_name, fpath))

    random.shuffle(flagged_files)
    random.shuffle(clean_files)

    if sample_n:
        n_flagged = min(len(flagged_files), int(sample_n * 0.6))
        n_clean = min(len(clean_files), sample_n - n_flagged)
        target = flagged_files[:n_flagged] + clean_files[:n_clean]
    else:
        target = flagged_files + clean_files[: len(flagged_files)]

    random.shuffle(target)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=100,
                         help="number of files to test")
    parser.add_argument("--model", type=str, default="llama-3.3-70b-versatile")
    parser.add_argument("--batch-size", type=int, default=None)
    parser.add_argument("--delay", type=float, default=None)
    parser.add_argument("--generate-dataset", action="store_true")
    args = parser.parse_args()

    dataset_path = os.path.join(RESULTS_DIR, "algorithms", "evaluation_dataset.json")

    if args.generate_dataset:
        targets = collect_target_files(sample_n=args.sample)
        dataset = [{"repo_name": r, "fpath": f} for r, f in targets]
        with open(dataset_path, "w") as f:
            json.dump(dataset, f, indent=2)
        print(f"Dataset of {len(targets)} files generated and saved to {dataset_path}")
        return

    if not os.path.exists(dataset_path):
        print(f"ERROR: {dataset_path} not found. Please run with --generate-dataset first.")
        sys.exit(1)

    with open(dataset_path, "r") as f:
        dataset = json.load(f)
        targets = [(d["repo_name"], d["fpath"]) for d in dataset]

    if args.batch_size is None or args.delay is None:
        if args.model.startswith("groq/"):
            auto_batch = 1
            auto_delay = 2.0
        elif args.model.startswith("gemini/"):
            auto_batch = 25
            auto_delay = 4.0
        elif args.model.startswith("mistral/"):
            auto_batch = 25
            auto_delay = 2.0
        elif args.model.startswith("cohere/"):
            # Increased to 15 to speed up processing, since command-r-plus-08-2024 has a high context window
            auto_batch = 15
            auto_delay = 2.0
        else:
            auto_batch = 1
            auto_delay = 2.0
            
        args.batch_size = args.batch_size or auto_batch
        args.delay = args.delay if args.delay is not None else auto_delay

    print(f"Running LLM detection on {len(targets)} files using {args.model}...")
    print(f"Configuration: batch_size={args.batch_size}, delay={args.delay}s\n")

    os.makedirs(os.path.join(RESULTS_DIR, "llm_findings"), exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "llm_findings", f"llm_findings_{args.model.replace('/', '_')}.json")
    
    results = {}
    if os.path.exists(out_path):
        try:
            with open(out_path, "r") as f:
                results = json.load(f)
            print(f"-> Resumed from checkpoint: {len(results)} files already processed.\n")
        except Exception:
            pass

    router = get_router(args.model)
    if router:
        print("-> litellm.Router active: Automatic Key Pooling is enabled.\n")

    for batch_idx in range(0, len(targets), args.batch_size):
        batch_targets = targets[batch_idx:batch_idx + args.batch_size]
        files_batch = []
        
        for repo_name, fpath in batch_targets:
            rel = os.path.relpath(fpath, os.path.join(REPOS_DIR, repo_name))
            full_key = f"{repo_name}/{rel}"
            
            # Skip if already processed via checkpointing
            if full_key in results:
                continue
                
            try:
                with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                    code = f.read()
                files_batch.append((full_key, code))
            except Exception as e:
                print(f"  [read error] {full_key}: {e}")

        if not files_batch:
            continue

        print(f"Processing batch {batch_idx//args.batch_size + 1} (Files {batch_idx + 1} to {min(len(targets), batch_idx + args.batch_size)})...")
        batch_flags = query_llm(args.model, files_batch, router=router, processed_total=len(results), target_total=len(targets))
        
        if batch_flags:
            results.update(batch_flags)
            # Save checkpoint instantly
            with open(out_path, "w") as f:
                json.dump(results, f, indent=2)
            
        if batch_idx + args.batch_size < len(targets):
            time.sleep(args.delay)

    print(f"\nDone. {len(results)} files processed. Saved to {out_path}")

if __name__ == "__main__":
    main()
