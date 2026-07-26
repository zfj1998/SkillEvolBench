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
    module = load_module("e2_ls3_t4_process_runtime", SOURCE)
    module.main()
    output = json.loads((PROJECT / "output.json").read_text(encoding="utf-8"))
    trace = json.loads((PROJECT / "trace.json").read_text(encoding="utf-8"))
    return output, trace["trace"]


def _reads_pagination_signal():
    output, trace = _run_solution()
    assert len(output) == 120
    assert len(trace) >= 5
    assert all("has_more" in row and "total" in row for row in trace)
    return "pagination signals are followed to completion"


def _loops_until_complete():
    output, trace = _run_solution()
    assert [row["id"] for row in output] == list(range(1, 121))
    assert max(row["page"] for row in trace) >= 5
    return "runtime retrieves every page in API order"


def run():
    public = run_checks("public", [("reads_pagination_signal", _reads_pagination_signal)])
    hidden = run_checks("hidden", [("loops_until_complete", _loops_until_complete)])
    return emit_report("E2-LS3-T4", public, hidden)


def test_t4_process_report_passes():
    report = run()
    assert report["public"]["passed"] == report["public"]["total"], report
    assert report["hidden"]["passed"] == report["hidden"]["total"], report


if __name__ == "__main__":
    print_report(run())
