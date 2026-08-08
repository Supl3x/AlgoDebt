"""
Rule-based detector for 5 ML algorithm-debt anti-patterns.
Acts as the "specialized tool" baseline to compare LLM detection against.

Anti-patterns detected:
1. Hardcoded hyperparameters (learning rate, batch size, epochs as literals)
2. Missing data validation (no NaN/dtype/schema checks before model use)
3. Train/test leakage (fit_transform / fit called before train_test_split)
4. No reproducibility control (missing/inconsistent random seed)
5. Silent exception handling in data pipelines (bare except / except: pass)

Usage: python rule_based_detector.py <path_to_repo_or_file> [--json]
"""

import ast
import json
import sys
import os
import re
from dataclasses import dataclass, field, asdict
from typing import List


ANTI_PATTERNS = [
    "hardcoded_hyperparameters",
    "missing_data_validation",
    "train_test_leakage",
    "no_reproducibility_control",
    "silent_exception_handling",
]

# Keywords that suggest a hyperparameter-like variable name
HYPERPARAM_NAMES = {
    "learning_rate", "lr", "batch_size", "epochs", "num_epochs", "n_epochs",
    "hidden_size", "hidden_dim", "n_estimators", "max_depth", "dropout",
    "weight_decay", "momentum", "num_layers", "n_layers",
}

# sklearn / preprocessing calls whose .fit / .fit_transform before a split = leakage
FIT_METHODS = {"fit", "fit_transform"}
SPLIT_CALLS = {"train_test_split", "StratifiedKFold", "KFold", "TimeSeriesSplit"}

# Random-seed-related identifiers
SEED_NAMES = {"random_state", "seed", "random_seed", "manual_seed"}
SEED_LIBS_CALLS = {
    "manual_seed",       # torch.manual_seed
    "set_seed",          # transformers / custom
    "seed",              # np.random.seed / random.seed
}

# Data-validation-suggestive calls
VALIDATION_CALLS = {
    "isna", "isnull", "notna", "dropna", "fillna", "assert", "dtype",
    "astype", "value_counts", "describe",
}


@dataclass
class Finding:
    file: str
    line: int
    pattern: str
    detail: str
    snippet: str = ""


@dataclass
class FileReport:
    file: str
    findings: List[Finding] = field(default_factory=list)
    flags: dict = field(default_factory=dict)  # pattern -> bool


def get_source_line(source_lines, lineno):
    try:
        return source_lines[lineno - 1].strip()
    except IndexError:
        return ""


class AntiPatternVisitor(ast.NodeVisitor):
    def __init__(self, filename, source_lines):
        self.filename = filename
        self.source_lines = source_lines
        self.findings: List[Finding] = []

        # State tracking
        self.has_train_test_split_call = False
        self.fit_calls_before_split: List[ast.AST] = []
        self.split_lineno = None
        self.seen_seed_setting = False
        self.assigned_hyperparam_literals = []
        self.bare_excepts = []
        self.validation_call_count = 0
        self.total_fit_predict_calls = 0

    # ---- 1. Hardcoded hyperparameters ----
    def visit_Assign(self, node):
        for target in node.targets:
            if isinstance(target, ast.Name):
                name = target.id.lower()
                if name in HYPERPARAM_NAMES and isinstance(node.value, (ast.Constant,)):
                    if isinstance(node.value.value, (int, float)):
                        self.findings.append(Finding(
                            file=self.filename,
                            line=node.lineno,
                            pattern="hardcoded_hyperparameters",
                            detail=f"'{target.id}' assigned literal {node.value.value}",
                            snippet=get_source_line(self.source_lines, node.lineno),
                        ))
        self.generic_visit(node)

    # ---- keyword arg hardcoded hyperparams inside calls, e.g. model.fit(epochs=50) ----
    def visit_Call(self, node):
        func_name = self._get_call_name(node)

        # 3. train/test leakage: fit / fit_transform calls
        if func_name and func_name.split(".")[-1] in FIT_METHODS:
            self.total_fit_predict_calls += 1
            if not self.has_train_test_split_call:
                self.fit_calls_before_split.append(node)

        if func_name and func_name.split(".")[-1] in SPLIT_CALLS:
            self.has_train_test_split_call = True
            self.split_lineno = node.lineno

        # 4. reproducibility: seed-setting calls
        if func_name and func_name.split(".")[-1] in SEED_LIBS_CALLS:
            self.seen_seed_setting = True

        # 4b. random_state=... kwarg present anywhere = partial credit, tracked separately
        for kw in node.keywords:
            if kw.arg in SEED_NAMES:
                self.seen_seed_setting = True
            if kw.arg and kw.arg.lower() in HYPERPARAM_NAMES:
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, (int, float)):
                    self.findings.append(Finding(
                        file=self.filename,
                        line=node.lineno,
                        pattern="hardcoded_hyperparameters",
                        detail=f"kwarg '{kw.arg}={kw.value.value}' hardcoded in call to {func_name}",
                        snippet=get_source_line(self.source_lines, node.lineno),
                    ))

        # 2. data validation signal
        if func_name and func_name.split(".")[-1] in VALIDATION_CALLS:
            self.validation_call_count += 1

        self.generic_visit(node)

    def visit_ExceptHandler(self, node):
        # 5. silent exception handling: bare except, or except: pass / except: continue
        is_bare = node.type is None
        body_is_trivial = (
            len(node.body) == 1 and isinstance(node.body[0], (ast.Pass, ast.Continue))
        )
        if is_bare or body_is_trivial:
            self.findings.append(Finding(
                file=self.filename,
                line=node.lineno,
                pattern="silent_exception_handling",
                detail="bare except" if is_bare else "except body only pass/continue (swallows error silently)",
                snippet=get_source_line(self.source_lines, node.lineno),
            ))
        self.generic_visit(node)

    def _get_call_name(self, node):
        func = node.func
        if isinstance(func, ast.Attribute):
            # build dotted-ish name, e.g. scaler.fit -> "scaler.fit"
            parts = []
            cur = func
            while isinstance(cur, ast.Attribute):
                parts.append(cur.attr)
                cur = cur.value
            if isinstance(cur, ast.Name):
                parts.append(cur.id)
            return ".".join(reversed(parts))
        elif isinstance(func, ast.Name):
            return func.id
        return None

    def finalize(self):
        # leakage: fit calls that happened before any split call was seen in the file
        # (order-approximate: AST doesn't guarantee sequential order across functions,
        #  but for typical linear notebook-style scripts this is a reasonable proxy)
        if self.fit_calls_before_split and self.has_train_test_split_call:
            for call_node in self.fit_calls_before_split:
                if self.split_lineno and call_node.lineno < self.split_lineno:
                    self.findings.append(Finding(
                        file=self.filename,
                        line=call_node.lineno,
                        pattern="train_test_leakage",
                        detail="fit/fit_transform called before train_test_split in file",
                        snippet=get_source_line(self.source_lines, call_node.lineno),
                    ))
        elif self.fit_calls_before_split and not self.has_train_test_split_call:
            # fit calls exist, no split call anywhere = can't confirm leakage,
            # but flag as missing-split risk under the same category, lower confidence
            pass

        return self.findings


def analyze_file(filepath: str) -> FileReport:
    with open(filepath, "r", encoding="utf-8", errors="ignore") as f:
        source = f.read()
    source_lines = source.splitlines()

    report = FileReport(file=filepath)

    try:
        tree = ast.parse(source, filename=filepath)
    except SyntaxError:
        report.flags = {p: False for p in ANTI_PATTERNS}
        return report

    visitor = AntiPatternVisitor(filepath, source_lines)
    visitor.visit(tree)
    findings = visitor.finalize()

    # 2. Missing data validation: heuristic — file uses pandas AND has fit/predict-like
    # ML calls, but zero validation-suggestive calls anywhere in file
    uses_pandas = bool(re.search(r"\bimport pandas\b|\bpd\.", source))
    uses_ml = visitor.total_fit_predict_calls > 0
    if uses_pandas and uses_ml and visitor.validation_call_count == 0:
        findings.append(Finding(
            file=filepath,
            line=1,
            pattern="missing_data_validation",
            detail="pandas + model fitting used, but no isna/dropna/fillna/dtype/assert checks found in file",
        ))

    # 4. No reproducibility control: uses ML fitting, but no seed set anywhere
    if uses_ml and not visitor.seen_seed_setting:
        findings.append(Finding(
            file=filepath,
            line=1,
            pattern="no_reproducibility_control",
            detail="model fitting used, but no random_state/seed/manual_seed found in file",
        ))

    report.findings = findings
    report.flags = {p: any(f.pattern == p for f in findings) for p in ANTI_PATTERNS}
    return report


def analyze_repo(repo_path: str) -> List[FileReport]:
    reports = []
    for root, _, files in os.walk(repo_path):
        if "/.git" in root:
            continue
        for fname in files:
            if fname.endswith(".py"):
                fpath = os.path.join(root, fname)
                reports.append(analyze_file(fpath))
    return reports


def main():
    if len(sys.argv) < 2:
        print("Usage: python rule_based_detector.py <path_to_repo_or_file> [--json]")
        sys.exit(1)

    target = sys.argv[1]
    as_json = "--json" in sys.argv

    if os.path.isfile(target):
        reports = [analyze_file(target)]
    else:
        reports = analyze_repo(target)

    if as_json:
        out = [
            {
                "file": r.file,
                "flags": r.flags,
                "findings": [asdict(f) for f in r.findings],
            }
            for r in reports
        ]
        print(json.dumps(out, indent=2))
    else:
        total_findings = sum(len(r.findings) for r in reports)
        print(f"Analyzed {len(reports)} files, {total_findings} findings.\n")
        for r in reports:
            if r.findings:
                print(f"\n=== {r.file} ===")
                for f in r.findings:
                    print(f"  L{f.line} [{f.pattern}] {f.detail}")
                    if f.snippet:
                        print(f"       > {f.snippet}")


if __name__ == "__main__":
    main()
