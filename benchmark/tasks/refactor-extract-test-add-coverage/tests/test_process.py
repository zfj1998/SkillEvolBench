from __future__ import annotations

import ast
import json
import shutil
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks, run_subprocess


SOURCE = PROJECT / "analyzer.py"


def _refactor_split():
    module = ast.parse(read_text(SOURCE))
    funcs = [node.name for node in module.body if isinstance(node, ast.FunctionDef)]
    assert len(funcs) >= 4, f"expected at least 4 functions, found {len(funcs)}"
    return funcs


def _tests_added():
    test_file = read_text(PROJECT / "public_tests" / "test_analyzer.py")
    count = test_file.count("def test_")
    assert count >= 8, f"expected at least 8 tests, found {count}"
    return {"test_count": count}


def _coverage_tooling_present():
    instruction = TASK_ROOT / "instruction.md"
    text = read_text(PROJECT / "public_tests" / "test_analyzer.py")
    if instruction.exists():
        text += read_text(instruction)
    assert "coverage" in text.lower(), "coverage-driven workflow not evident"
    return "coverage references present"


def _coverage_threshold_met():
    coverage = shutil.which("coverage")
    if not coverage:
        return "coverage executable unavailable in environment; threshold check deferred"
    data_file = PROJECT / ".coverage.verifier"
    run = run_subprocess(
        [coverage, "run", f"--data-file={data_file}", "-m", "pytest", "public_tests"],
        PROJECT,
    )
    assert run.returncode == 0, run.stdout + run.stderr
    report = run_subprocess(
        [coverage, "json", f"--data-file={data_file}", "-o", "-"],
        PROJECT,
    )
    assert report.returncode == 0, report.stdout + report.stderr
    payload = json.loads(report.stdout)
    percent = payload["totals"]["percent_covered"]
    assert percent >= 90.0, f"coverage {percent:.2f}% is below 90%"
    return {"percent_covered": percent}


def _edge_case_test_names_present():
    text = read_text(PROJECT / "public_tests" / "test_analyzer.py")
    expected = ["empty", "single", "equal", "negative"]
    found = [word for word in expected if word in text.lower()]
    assert len(found) >= 3, f"expected more edge-case-oriented tests, found {found}"
    return found


def run():
    public = run_checks("public", [("refactor_split", _refactor_split)])
    hidden = run_checks(
        "hidden",
        [
            ("tests_added", _tests_added),
            ("coverage_tooling_present", _coverage_tooling_present),
            ("coverage_threshold_met", _coverage_threshold_met),
            ("edge_case_test_names_present", _edge_case_test_names_present),
        ],
    )
    return emit_report("E1-LS3-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
