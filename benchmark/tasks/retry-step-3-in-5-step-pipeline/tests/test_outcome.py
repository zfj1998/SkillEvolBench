from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
for item in (SKILLSBENCH_ROOT, PROJECT):
    if str(item) not in sys.path:
        sys.path.insert(0, str(item))

from mock_pipeline import PipelineAPI
from pipeline_client import run_pipeline
from verifier_lib.runtime import emit_report, print_report, run_checks


def _run_case():
    api = PipelineAPI()
    result = run_pipeline(api, max_retries=2)
    return result, api


def run():
    public = run_checks(
        "public",
        [
            ("pipeline_succeeds", lambda: _run_case()[0]["saved"] == 2 or (_ for _ in ()).throw(AssertionError("expected two saved rows"))),
            ("all_steps_finish", lambda: {row["step"] for row in _run_case()[1].trace} >= {"auth", "list", "detail", "enrich", "save"} or (_ for _ in ()).throw(AssertionError("expected all pipeline steps"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("step1_runs_once", lambda: _run_case()[1].step_counts["auth"] == 1 or (_ for _ in ()).throw(AssertionError("auth should not rerun"))),
            ("step2_runs_once", lambda: _run_case()[1].step_counts["list"] == 1 or (_ for _ in ()).throw(AssertionError("list should not rerun"))),
            ("step3_retries_only_once", lambda: _run_case()[1].step_counts["detail"] == 2 or (_ for _ in ()).throw(AssertionError("detail should run twice"))),
            ("step4_runs_once", lambda: _run_case()[1].step_counts["enrich"] == 1 or (_ for _ in ()).throw(AssertionError("enrich should run once"))),
            ("step5_and_payload_correct", lambda: _run_case()[1].step_counts["save"] == 1 and all(row["enriched"] for row in _run_case()[0]["rows"]) or (_ for _ in ()).throw(AssertionError("save result incorrect"))),
        ],
    )
    return emit_report("E2-LS2-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
