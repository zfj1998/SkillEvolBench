from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from batch_import import import_batch
from verifier_lib.runtime import emit_report, print_report, run_checks


DATA = PROJECT / "employees.json"


def _result():
    return import_batch(DATA)


def run():
    public = run_checks(
        "public",
        [
            ("summary_exists", lambda: "summary" in _result() or (_ for _ in ()).throw(AssertionError("summary missing"))),
            ("failures_exists", lambda: "failures" in _result() or (_ for _ in ()).throw(AssertionError("failures missing"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("exact_success_count", lambda: len(_result()["success"]) == 4 or (_ for _ in ()).throw(AssertionError("expected 4 successes"))),
            ("exact_summary_counts", lambda: _result()["summary"] == {"total": 10, "succeeded": 4, "failed": 6} or (_ for _ in ()).throw(AssertionError(f"bad summary: {_result()['summary']!r}"))),
            ("duplicate_reason_present", lambda: any(any(err.get("reason") == "duplicate" for err in item.get("errors", [])) for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("duplicate reason missing"))),
            ("later_duplicate_rejected_after_prior_success", lambda: any(item.get("index") == 6 and any(err.get("reason") == "duplicate" for err in item.get("errors", [])) for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("later duplicate username should be rejected after earlier success"))),
            ("empty_vs_missing_distinguished", lambda: any(any(err.get("reason") == "empty" for err in item.get("errors", [])) for item in _result()["failures"]) and any(any(err.get("reason") == "missing" for err in item.get("errors", [])) for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("empty vs missing not distinguished"))),
            ("failure_entries_include_index", lambda: all("index" in item for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("each failure should include original index"))),
            ("failure_errors_have_field_and_reason", lambda: all(all("field" in err and "reason" in err for err in item.get("errors", [])) for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("each validation error should include field and reason"))),
            ("bad_email_format_reason_present", lambda: any(any(err.get("field") == "email" and err.get("reason") in {"format", "invalid_format", "bad_format", "bad_email_format"} for err in item.get("errors", [])) for item in _result()["failures"]) or (_ for _ in ()).throw(AssertionError("bad email format reason missing"))),
        ],
    )
    return emit_report("E2-LS1-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
