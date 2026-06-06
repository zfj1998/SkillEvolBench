from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


SOURCE = PROJECT / "client.py"


def _validation_before_fetch():
    text = read_text(SOURCE)
    assert text.index("errors = validate_request") < text.index("successes.append(fetch_weather"), "validation should happen before fetch_weather call"
    return "validation precedes fetch"


def _structured_error_shape():
    text = read_text(SOURCE)
    assert "param" in text and "error" in text and "value" in text and "expected" in text, "structured error fields incomplete"
    return "structured error fields present"


def _not_remote_400_driven():
    text = read_text(SOURCE)
    assert "try:" not in text and "except" not in text, "implementation should not use remote exception flow as validation"
    return "no remote-error-driven validation"


def _multiple_error_collection():
    text = read_text(SOURCE)
    assert "errors.append(" in text, "expected collection of multiple field errors"
    return "multiple errors can be collected"


def run():
    public = run_checks("public", [("validation_before_fetch", _validation_before_fetch)])
    hidden = run_checks(
        "hidden",
        [
            ("structured_error_shape", _structured_error_shape),
            ("not_remote_400_driven", _not_remote_400_driven),
            ("multiple_error_collection", _multiple_error_collection),
        ],
    )
    return emit_report("E2-LS1-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
