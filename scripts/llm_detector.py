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

For the Python file given, check for these 5 specific anti-patterns:

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

Respond with ONLY a JSON object, no other text, no markdown fences, in this exact \
format:
{
  "hardcoded_hyperparameters": true/false,
  "missing_data_validation": true/false,
  "train_test_leakage": true/false,
  "no_reproducibility_control": true/false,
  "silent_exception_handling": true/false
}
"""


def get_client():
    from groq import Groq
    api_key = os.environ.get("GROQ_API_KEY")
    if not api_key:
        print("ERROR: set GROQ_API_KEY environment variable first.")
        sys.exit(1)
    return Groq(api_key=api_key)


def query_llm(client, model, code, filename, max_retries=3):
    truncated = code[:12000]  # keep prompt reasonable for long files
    user_prompt = f"File: {filename}\n\n```python\n{truncated}\n```"

    for attempt in range(max_retries):
        try:
            resp = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": user_prompt},
                ],
                temperature=0,
                max_tokens=300,
            )
            text = resp.choices[0].message.content.strip()
            # strip markdown fences if the model adds them anyway
            text = re.sub(r"^```json\s*|\s*```$", "", text.strip())
            parsed = json.loads(text)
            return {p: bool(parsed.get(p, False)) for p in ANTI_PATTERNS}
        except json.JSONDecodeError:
            if attempt == max_retries - 1:
                print(f"  [parse failed] {filename}: {text[:100]}")
                return None
        except Exception as e:
            wait = 2 ** attempt
            print(f"  [retry {attempt+1}] {filename}: {e} (waiting {wait}s)")
            time.sleep(wait)
    return None


def collect_target_files(sample_n=None, use_baseline_flagged=True):
    """Pick files to run through the LLM: prioritize files the rule-based
    detector flagged, plus a random sample of clean files for balance
    (so recall AND false-positive rate can both be measured fairly)."""
    baseline_path = os.path.join(RESULTS_DIR, "rule_based_findings.json")
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
        target = flagged_files + clean_files[: len(flagged_files)]  # 1:1 balance

    random.shuffle(target)
    return target


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--sample", type=int, default=100,
                         help="number of files to test (mix of flagged + clean)")
    parser.add_argument("--model", type=str, default="llama-3.3-70b-versatile",
                         help="Groq model name")
    args = parser.parse_args()

    client = get_client()
    targets = collect_target_files(sample_n=args.sample)
    print(f"Running LLM detection on {len(targets)} files using {args.model}...\n")

    results = {}
    for i, (repo_name, fpath) in enumerate(targets, 1):
        rel = os.path.relpath(fpath, os.path.join(REPOS_DIR, repo_name))
        print(f"[{i}/{len(targets)}] {repo_name}/{rel}")
        try:
            with open(fpath, "r", encoding="utf-8", errors="ignore") as f:
                code = f.read()
        except Exception as e:
            print(f"  [read error] {e}")
            continue

        flags = query_llm(client, args.model, code, rel)
        if flags is not None:
            results[f"{repo_name}/{rel}"] = flags
        time.sleep(1)  # be polite to rate limits

    out_path = os.path.join(RESULTS_DIR, "llm_findings.json")
    with open(out_path, "w") as f:
        json.dump(results, f, indent=2)

    print(f"\nDone. {len(results)} files processed. Saved to {out_path}")


if __name__ == "__main__":
    main()
