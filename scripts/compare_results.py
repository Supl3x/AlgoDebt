"""
Compares rule-based detector output (treated as ground truth) against LLM
detector output, computing precision/recall/F1 per anti-pattern.

Usage: python compare_results.py
Reads: results/rule_based_findings.json, results/llm_findings.json
Writes: results/comparison_report.json, prints summary table + disagreements
"""

import json
import os

RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")

ANTI_PATTERNS = [
    "hardcoded_hyperparameters",
    "missing_data_validation",
    "train_test_leakage",
    "no_reproducibility_control",
    "silent_exception_handling",
]


def load_rule_based_flags():
    """Returns dict: 'repo_name/relpath' -> {pattern: bool}"""
    path = os.path.join(RESULTS_DIR, "algorithms", "rule_based_findings.json")
    with open(path) as f:
        baseline = json.load(f)

    flags_by_file = {}
    for repo_name, repo_data in baseline.items():
        flagged_files = {f["file"]: f["flags"] for f in repo_data["findings"]}
        # rule_based_findings.json only stores files WITH findings;
        # llm_findings.json may include clean files too, so default to all-False
        for rel, flags in flagged_files.items():
            file_key = f"{repo_name}/{rel}".replace("\\", "/")
            flags_by_file[file_key] = flags
    return flags_by_file


def main():
    import argparse
    import sys
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", type=str, required=True,
                         help="Model name to compare results for (e.g. llama-3.3-70b-versatile)")
    parser.add_argument("--results-dir", type=str, default=RESULTS_DIR,
                         help="Directory containing algorithms, llm_findings, and comparison_reports")
    parser.add_argument("--suffix", type=str, default="",
                         help="Suffix for findings/report files (e.g. '_role_filtered')")
    args = parser.parse_args()

    rule_flags = load_rule_based_flags()

    safe_model_name = args.model.replace("/", "_").replace(":", "_")
    llm_path = os.path.join(args.results_dir, "llm_findings", f"llm_findings_{safe_model_name}{args.suffix}.json")
    if not os.path.exists(llm_path):
        print(f"ERROR: {llm_path} not found. Run llm_detector.py with this model first.")
        sys.exit(1)
        
    with open(llm_path) as f:
        llm_flags_raw = json.load(f)
        llm_flags = {k.replace("\\", "/"): v for k, v in llm_flags_raw.items()}

    # Confusion matrix counts per pattern
    stats = {p: {"tp": 0, "fp": 0, "fn": 0, "tn": 0} for p in ANTI_PATTERNS}
    disagreements = []

    for file_key, llm_result in llm_flags.items():
        # files not in rule_flags are ones the rule-based tool found NO issues in
        # (i.e. all flags = False), since rule_based_findings.json only stores
        # files that had at least one finding
        rb_result = rule_flags.get(file_key, {p: False for p in ANTI_PATTERNS})

        for p in ANTI_PATTERNS:
            llm_says = bool(llm_result.get(p, False))
            rb_says = bool(rb_result.get(p, False))

            if llm_says and rb_says:
                stats[p]["tp"] += 1
            elif llm_says and not rb_says:
                stats[p]["fp"] += 1
                disagreements.append({"file": file_key, "pattern": p, "type": "LLM said yes, rule-based said no"})
            elif not llm_says and rb_says:
                stats[p]["fn"] += 1
                disagreements.append({"file": file_key, "pattern": p, "type": "LLM said no, rule-based said yes"})
            else:
                stats[p]["tn"] += 1

    print(f"Compared {len(llm_flags)} files.\n")
    print(f"{'Anti-pattern':30s} {'Precision':>10s} {'Recall':>10s} {'F1':>8s} {'TP':>5s} {'FP':>5s} {'FN':>5s} {'TN':>5s}")
    print("-" * 90)

    report = {}
    for p in ANTI_PATTERNS:
        tp, fp, fn, tn = stats[p]["tp"], stats[p]["fp"], stats[p]["fn"], stats[p]["tn"]
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

        report[p] = {
            "precision": round(precision, 3),
            "recall": round(recall, 3),
            "f1": round(f1, 3),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        }
        print(f"{p:30s} {precision:>10.2f} {recall:>10.2f} {f1:>8.2f} {tp:>5d} {fp:>5d} {fn:>5d} {tn:>5d}")

    os.makedirs(os.path.join(args.results_dir, "comparison_reports"), exist_ok=True)
    out_path = os.path.join(args.results_dir, "comparison_reports", f"comparison_report_{safe_model_name}{args.suffix}.json")
    with open(out_path, "w") as f:
        json.dump({"stats": report, "disagreements": disagreements}, f, indent=2)

    print(f"\nSaved full report + {len(disagreements)} disagreement cases to {out_path}")
    print("Disagreement cases are worth spot-checking manually for your Discussion section —")
    print("they usually reveal WHY the LLM misses or over-flags certain pattern types.")


if __name__ == "__main__":
    main()
