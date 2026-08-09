"""
Applies file-role classification to existing LLM findings.
For each file, looks up its classified role and forces ineligible anti-pattern
flags to False based on the role-eligibility matrix.

Usage:
  python apply_role_filter.py --results-dir results/archive/batch_1 --model gemini/gemini-3.5-flash

  To use one model's classification for another model's findings:
  python apply_role_filter.py --results-dir results/archive/batch_1 --model mistral/mistral-large-latest --roles-model gemini/gemini-3.5-flash
"""

import argparse
import json
import os
import sys

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

ANTI_PATTERNS = [
    "hardcoded_hyperparameters",
    "missing_data_validation",
    "train_test_leakage",
    "no_reproducibility_control",
    "silent_exception_handling",
]

ROLE_ELIGIBLE_PATTERNS = {
    "training_script":    {"hardcoded_hyperparameters", "missing_data_validation",
                           "train_test_leakage", "no_reproducibility_control",
                           "silent_exception_handling"},
    "data_pipeline":      {"missing_data_validation", "train_test_leakage",
                           "silent_exception_handling"},
    "model_architecture": {"hardcoded_hyperparameters", "silent_exception_handling"},
    "utility":            {"silent_exception_handling"},
    "test":               set(),
    "config":             set(),
}


def main():
    parser = argparse.ArgumentParser(description="Apply role-based filtering to LLM findings.")
    parser.add_argument("--model", type=str, required=True,
                         help="Detection model name (e.g. gemini/gemini-3.5-flash)")
    parser.add_argument("--results-dir", type=str, default=RESULTS_DIR,
                         help="Directory containing llm_findings/")
    parser.add_argument("--roles-file", type=str, default=None,
                         help="Direct path to file_roles JSON (overrides auto-detection)")
    parser.add_argument("--roles-model", type=str, default=None,
                         help="Model used for classification (defaults to --model)")
    args = parser.parse_args()

    safe_model_name = args.model.replace("/", "_").replace(":", "_")
    findings_dir = os.path.join(args.results_dir, "llm_findings")

    # Load roles
    if args.roles_file:
        roles_path = args.roles_file
    else:
        roles_model = args.roles_model or args.model
        safe_roles_model = roles_model.replace("/", "_").replace(":", "_")
        roles_path = os.path.join(findings_dir, f"file_roles_{safe_roles_model}.json")

    if not os.path.exists(roles_path):
        print(f"ERROR: Roles file not found: {roles_path}")
        print("Run llm_detector.py --classify first to generate file classifications.")
        sys.exit(1)

    with open(roles_path, "r") as f:
        roles = json.load(f)

    # Load original findings
    findings_path = os.path.join(findings_dir, f"llm_findings_{safe_model_name}.json")
    if not os.path.exists(findings_path):
        print(f"ERROR: Findings file not found: {findings_path}")
        sys.exit(1)

    with open(findings_path, "r") as f:
        findings = json.load(f)

    # Normalize keys (handle Windows backslash vs forward slash)
    roles_normalized = {k.replace("\\", "/"): v for k, v in roles.items()}
    findings_normalized = {k.replace("\\", "/"): v for k, v in findings.items()}

    # Apply filter
    filtered = {}
    stats = {"total": 0, "skipped_fully": 0, "patterns_suppressed": 0, "unclassified": 0}

    for file_key, flags in findings_normalized.items():
        stats["total"] += 1
        role = roles_normalized.get(file_key)

        if role is None:
            # File not classified — keep original flags (conservative)
            filtered[file_key] = flags
            stats["unclassified"] += 1
            continue

        eligible = ROLE_ELIGIBLE_PATTERNS.get(role, ROLE_ELIGIBLE_PATTERNS["training_script"])
        new_flags = {}
        file_suppressed = 0

        for pattern in ANTI_PATTERNS:
            if pattern in eligible:
                new_flags[pattern] = flags.get(pattern, False)
            else:
                if flags.get(pattern, False):
                    file_suppressed += 1
                new_flags[pattern] = False

        filtered[file_key] = new_flags
        stats["patterns_suppressed"] += file_suppressed

        if not eligible:
            stats["skipped_fully"] += 1

    # Save filtered findings
    out_path = os.path.join(findings_dir, f"llm_findings_{safe_model_name}_role_filtered.json")
    with open(out_path, "w") as f:
        json.dump(filtered, f, indent=2)

    print(f"Role filter applied to {stats['total']} files.")
    print(f"  Files fully skipped (test/config): {stats['skipped_fully']}")
    print(f"  Individual pattern flags suppressed: {stats['patterns_suppressed']}")
    print(f"  Files without role classification: {stats['unclassified']}")
    print(f"\nFiltered findings saved to {out_path}")
    print(f"\nTo compare: python compare_results.py --model {args.model} --results-dir {args.results_dir} --suffix _role_filtered")


if __name__ == "__main__":
    main()
