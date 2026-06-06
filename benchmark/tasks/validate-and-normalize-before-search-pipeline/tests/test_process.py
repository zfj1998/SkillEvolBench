from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "pipeline.py"


def _parameter_extraction_present():
    text = read_text(SOURCE)
    assert "extract_params" in text, "parameter extraction step missing"
    return "extract_params present"


def _validation_present():
    text = read_text(SOURCE)
    assert "validate" in text, "explicit validation step missing"
    return "validation step present"


def _no_malformed_calls():
    text = read_text(SOURCE)
    assert '"state": "California"' not in text, "hardcoded unnormalized state indicates malformed call risk"
    return "no obvious malformed state"


def _normalize_helper_present():
    text = read_text(SOURCE)
    assert "normalize_params" in text, "normalize_params helper missing"
    return "normalize helper present"


def run():
    public = run_checks("public", [("parameter_extraction_present", _parameter_extraction_present)])
    hidden = run_checks(
        "hidden",
        [
            ("validation_present", _validation_present),
            ("no_malformed_calls", _no_malformed_calls),
            ("normalize_helper_present", _normalize_helper_present),
        ],
    )
    return emit_report("E2-LS1-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
