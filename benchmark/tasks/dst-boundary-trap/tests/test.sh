#!/bin/bash
# Slim test runner v2 -- writes the 3 report files VerifierAdapter expects:
#   reward.txt              canonical Harbor reward (verifier_passed = reward >= 1.0)
#   score_report.json       {passed, total, reward, dimensions: [outcome, process]}
#   outcome_report.json     {public: {passed, total, results: [...]}}
#   process_report.json     {public: {passed, total, results: [...]}}
#
# Replaces the v1 slim runner (one merged list, no group split) used by the
# 60 E5+E6 tasks. v2 keeps the same in-file convention -- test_outcome.py
# holds outcome-group tests, test_process.py holds process-group tests --
# but emits separate report files so SkillAuthor.process feedback gets the
# outcome/process split + per-dim score it needs.
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
LOG_DIR="${HARBOR_LOG_DIR:-/logs/verifier}"
PYTHON_BIN="${PYTHON_BIN:-python3}"
mkdir -p "$LOG_DIR"
export PYTHONDONTWRITEBYTECODE=1
export SCRIPT_DIR PROJECT_ROOT LOG_DIR PYTHON_BIN
"$PYTHON_BIN" - <<'PY'
from __future__ import annotations
import importlib.util
import json
import os
from pathlib import Path

script_dir = Path(os.environ["SCRIPT_DIR"])
project_root = Path(os.environ["PROJECT_ROOT"])
log_dir = Path(os.environ["LOG_DIR"])
os.chdir(project_root)


def load_module(path: Path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


def run_module(path: Path):
    """Return (results_for_score_json, results_for_report_json).

    score_json result format (back-compat with slim v1):
      {"name": "...", "outcome": "passed"|"failed", "error"?: "..."}

    report_json result format (what VerifierAdapter._failed_from_script_report wants):
      {"name": "...", "passed": bool, "error": str}
    """
    if not path.exists():
        return [], []
    module = load_module(path)
    score_results = []
    report_results = []

    def _record(name: str, ok: bool, err: str = ""):
        if ok:
            score_results.append({"name": name, "outcome": "passed"})
            report_results.append({"name": name, "passed": True})
        else:
            score_results.append({"name": name, "outcome": "failed", "error": err})
            report_results.append({"name": name, "passed": False, "error": err})

    if hasattr(module, "setup_module"):
        try:
            module.setup_module()
            _record(f"{path.name}.setup_module", True)
        except Exception as exc:
            _record(f"{path.name}.setup_module", False, f"{type(exc).__name__}: {exc}")

    for attr_name in sorted(dir(module)):
        attr = getattr(module, attr_name)
        if isinstance(attr, type) and attr_name.startswith("Test"):
            instance = attr()
            for test_name in sorted(name for name in dir(attr) if name.startswith("test_")):
                full = f"{attr_name}.{test_name}"
                try:
                    getattr(instance, test_name)()
                    _record(full, True)
                except AssertionError as exc:
                    _record(full, False, str(exc))
                except Exception as exc:
                    _record(full, False, f"{type(exc).__name__}: {exc}")

    return score_results, report_results


outcome_score, outcome_report = run_module(script_dir / "test_outcome.py")
process_score, process_report = run_module(script_dir / "test_process.py")

outcome_passed = sum(1 for r in outcome_score if r["outcome"] == "passed")
outcome_total = len(outcome_score)
process_passed = sum(1 for r in process_score if r["outcome"] == "passed")
process_total = len(process_score)

total = outcome_total + process_total
passed = outcome_passed + process_passed
reward = 0.0 if total == 0 else round(passed / total, 4)

# 1. reward.txt  (canonical Harbor signal)
(log_dir / "reward.txt").write_text(f"{reward:.4f}\n", encoding="utf-8")

# 2. outcome_report.json + process_report.json
#    Shape: {"public": {"passed": int, "total": int, "results": [{name, passed, error?}]}}
#    All slim tasks lack a public/hidden split, so everything goes into "public".
def _report_doc(passed: int, total: int, results: list) -> dict:
    return {"public": {"passed": passed, "total": total, "results": results}}

(log_dir / "outcome_report.json").write_text(
    json.dumps(_report_doc(outcome_passed, outcome_total, outcome_report), indent=2),
    encoding="utf-8",
)
(log_dir / "process_report.json").write_text(
    json.dumps(_report_doc(process_passed, process_total, process_report), indent=2),
    encoding="utf-8",
)

# 3. score_report.json with dimensions  (50/50 outcome:process by default)
#    Per-dim scoring: ratio = passed/total; score = ratio * weight.
def _dim(name: str, weight: float, p: int, t: int) -> dict:
    ratio = (p / t) if t > 0 else 0.0
    return {
        "name": name,
        "weight": weight,
        "tests_matched": t,
        "tests_passed": p,
        "ratio": round(ratio, 4),
        "score": round(ratio * weight, 4),
        "scoring": "proportional",
    }

dimensions = [
    _dim("outcome", 0.5, outcome_passed, outcome_total),
    _dim("process", 0.5, process_passed, process_total),
]

# Back-compat: keep the flat ``tests`` list slim v1 used to write.
(log_dir / "score_report.json").write_text(
    json.dumps({
        "passed": passed,
        "total": total,
        "reward": reward,
        "dimensions": dimensions,
        "tests": outcome_score + process_score,
    }, indent=2),
    encoding="utf-8",
)

print(json.dumps({
    "passed": passed, "total": total, "reward": reward,
    "outcome": {"passed": outcome_passed, "total": outcome_total},
    "process": {"passed": process_passed, "total": process_total},
}))
PY
