from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from verifier_lib.runtime import emit_report, print_report, run_checks
from pipeline import format_output, parse, run_pipeline, transform


def run():
    public = run_checks(
        "public",
        [
            ("json_string_runs", lambda: '"_transformed": true' in run_pipeline('{"name":"alice"}') or (_ for _ in ()).throw(AssertionError("expected transformed json"))),
            ("dict_runs", lambda: '"name": "bob"' in run_pipeline({"name": "bob"}) or (_ for _ in ()).throw(AssertionError("expected dict output"))),
            ("empty_string_runs", lambda: run_pipeline("") == '{"_default": true}' or (_ for _ in ()).throw(AssertionError(f"run_pipeline('') incorrect: {run_pipeline('')!r}"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("parse_none_is_empty_dict", lambda: parse(None) == {} or (_ for _ in ()).throw(AssertionError(f"expected {{}}, got {parse(None)!r}"))),
            ("transform_none_is_none", lambda: transform(None) is None or (_ for _ in ()).throw(AssertionError("transform(None) should be None"))),
            ("format_none_empty_string", lambda: format_output(None) == "" or (_ for _ in ()).throw(AssertionError("format_output(None) should be empty string"))),
            ("run_none_preserves_chain", lambda: run_pipeline(None) == '{"_default": true}' or (_ for _ in ()).throw(AssertionError(f"run_pipeline(None) incorrect: {run_pipeline(None)!r}"))),
            ("empty_dict_semantics", lambda: transform({}) == {"_default": True} or (_ for _ in ()).throw(AssertionError("empty dict should get default marker"))),
        ],
    )
    return emit_report("E1-LS3-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
