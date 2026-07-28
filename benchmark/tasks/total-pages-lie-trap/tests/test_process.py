from __future__ import annotations

import json
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, load_module, print_report, run_checks

SOURCE = PROJECT / "solution.py"


def _run_solution():
    for path in (PROJECT / "output.json", PROJECT / "trace.json"):
        if path.exists():
            path.unlink()
    module = load_module("e2_ls3_t5_process_runtime", SOURCE)
    module.main()
    output = json.loads((PROJECT / "output.json").read_text(encoding="utf-8"))
    trace = json.loads((PROJECT / "trace.json").read_text(encoding="utf-8"))
    return output, trace["trace"]


def _rechecks_metadata_or_has_more():
    output, trace = _run_solution()
    assert len(output) == 80
    assert [row["page"] for row in trace] == list(range(1, 9))
    return "pagination state is rechecked through page 8"


def _not_hardcoded_to_first_total_pages():
    output, trace = _run_solution()
    assert len(trace) == 8 and len(output) == 80
    return "runtime does not stop at the stale first-page total"


def run():
    public = run_checks("public", [("rechecks_metadata_or_has_more", _rechecks_metadata_or_has_more)])
    hidden = run_checks("hidden", [("not_hardcoded_to_first_total_pages", _not_hardcoded_to_first_total_pages)])
    return emit_report("E2-LS3-T5", public, hidden)


def test_t5_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
