"""
Runs rule_based_detector across all repos in ../repos/, saves per-file results
to results/rule_based_findings.json and prints summary stats per anti-pattern.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
from rule_based_detector import analyze_repo, ANTI_PATTERNS  # noqa

REPOS_DIR = os.path.join(os.path.dirname(__file__), "..", "repos")
RESULTS_DIR = os.path.join(os.path.dirname(__file__), "..", "results")


def main():
    all_results = {}
    pattern_file_counts = {p: 0 for p in ANTI_PATTERNS}
    total_files = 0

    repo_dirs = [
        d for d in sorted(os.listdir(REPOS_DIR))
        if os.path.isdir(os.path.join(REPOS_DIR, d))
    ]

    for repo_name in repo_dirs:
        repo_path = os.path.join(REPOS_DIR, repo_name)
        reports = analyze_repo(repo_path)
        total_files += len(reports)

        repo_result = []
        for r in reports:
            if r.findings:
                repo_result.append({
                    "file": os.path.relpath(r.file, repo_path),
                    "flags": r.flags,
                    "findings": [
                        {"line": f.line, "pattern": f.pattern, "detail": f.detail, "snippet": f.snippet}
                        for f in r.findings
                    ],
                })
            for p in ANTI_PATTERNS:
                if r.flags.get(p):
                    pattern_file_counts[p] += 1

        all_results[repo_name] = {
            "n_python_files": len(reports),
            "n_files_with_findings": len(repo_result),
            "findings": repo_result,
        }

    os.makedirs(RESULTS_DIR, exist_ok=True)
    out_path = os.path.join(RESULTS_DIR, "rule_based_findings.json")
    with open(out_path, "w") as f:
        json.dump(all_results, f, indent=2)

    print(f"Analyzed {len(repo_dirs)} repos, {total_files} total Python files.\n")
    print("Files flagged per anti-pattern (rule-based baseline):")
    for p in ANTI_PATTERNS:
        pct = (pattern_file_counts[p] / total_files * 100) if total_files else 0
        print(f"  {p:30s} {pattern_file_counts[p]:4d} files  ({pct:.1f}%)")

    print(f"\nSaved detailed results to {out_path}")


if __name__ == "__main__":
    main()
