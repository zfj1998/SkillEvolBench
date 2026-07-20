from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.metrics.reflection_transfer import (
    compute_reflection_transfer,
)
from skillevolbench.metrics.reporter import ReportGenerator
from skillevolbench.schemas import (
    ReplayRecord,
    RunConfig,
    StrategyConfig,
    TrialOutcome,
)
from skillevolbench.stores import EventStore, ReplayStore


REPO_ROOT = Path(__file__).resolve().parents[1]
ROLE_BY_TIER = {
    "T1": "canonical",
    "T2": "enriched",
    "T3": "variant",
    "T4": "context-shift",
    "T5": "adversarial",
    "T6": "composition",
}


def _record(
    task_id: str,
    *,
    passed: bool,
    offset: int,
    reflection_status: str | None = None,
    replay_mode: str = "primary",
) -> ReplayRecord:
    tier = task_id.split("__", 1)[0].rsplit("-", 1)[-1]
    reflection = (
        {"status": reflection_status} if reflection_status is not None else {}
    )
    return ReplayRecord(
        task_id=task_id,
        family_id="-".join(task_id.split("-")[:2]),
        env_id=task_id.split("-", 1)[0],
        task_role=ROLE_BY_TIER[tier],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=offset),
        outcome=TrialOutcome(task_id=task_id, verifier_passed=passed),
        reflection=reflection,
        replay_mode=replay_mode,
    )


def test_reflection_transfer_counts_every_terminal_status() -> None:
    records = [
        _record(
            "E1-LS1-T1", passed=False, offset=1,
            reflection_status="completed",
        ),
        _record(
            "E1-LS1-T2", passed=True, offset=2,
            reflection_status="noop",
        ),
        # A replay between T2 and T3 must never become the transfer target.
        _record(
            "E1-LS1-T2__replay", passed=True, offset=3,
            reflection_status="completed", replay_mode="within_env_replay",
        ),
        _record(
            "E1-LS1-T3", passed=False, offset=4,
            reflection_status="rejected",
        ),
        _record("E1-LS1-T4", passed=False, offset=5),
        _record(
            "E1-LS2-T1", passed=True, offset=6,
            reflection_status="skipped",
        ),
        _record("E1-LS2-T2", passed=True, offset=7),
    ]

    report = compute_reflection_transfer(records)

    assert report.n_pairs == 4
    assert report.fail_to_success_count == 1
    assert report.fail_to_fail_count == 1
    assert report.success_to_success_count == 1
    assert report.success_to_fail_count == 1
    assert report.failure_recovery_rate == pytest.approx(0.5)
    assert report.success_regression_rate == pytest.approx(0.5)

    by_status = report.by_reflection_status
    assert by_status["completed"].fail_to_success_count == 1
    assert by_status["completed"].failure_recovery_rate == 1.0
    assert by_status["noop"].success_to_fail_count == 1
    assert by_status["noop"].success_regression_rate == 1.0
    assert by_status["rejected"].fail_to_fail_count == 1
    assert by_status["rejected"].failure_recovery_rate == 0.0
    assert by_status["skipped"].success_to_success_count == 1
    assert by_status["skipped"].success_regression_rate == 0.0
    assert [pair.next_task_id for pair in report.pairs[:3]] == [
        "E1-LS1-T2",
        "E1-LS1-T3",
        "E1-LS1-T4",
    ]


def test_reflection_transfer_rates_are_none_without_matching_source_class() -> None:
    report = compute_reflection_transfer(
        [
            _record(
                "E1-LS1-T1", passed=False, offset=1,
                reflection_status="noop",
            ),
            _record("E1-LS1-T2", passed=True, offset=2),
        ]
    )

    assert report.failure_recovery_rate == 1.0
    assert report.success_regression_rate is None
    assert report.by_reflection_status["completed"].n_pairs == 0
    assert (
        report.by_reflection_status["completed"].failure_recovery_rate is None
    )


def test_reporter_strictly_verifies_sessions_and_treats_noop_as_valid(
    tmp_path: Path,
) -> None:
    config = RunConfig(
        run_id="reflection-report",
        baseline=load_baseline("selfgen_in_session_always"),
        strategy=StrategyConfig.from_yaml(
            REPO_ROOT / "configs" / "strategies" / "chain.yaml"
        ),
        environment_id="E1",
        workspace_root=tmp_path,
    )
    run_root = config.run_dir
    replay = ReplayStore(run_root / "stores" / "replay")
    for record in (
        _record(
            "E1-LS1-T1", passed=False, offset=1,
            reflection_status="completed",
        ),
        _record(
            "E1-LS1-T2", passed=True, offset=2,
            reflection_status="noop",
        ),
        _record(
            "E1-LS1-T3", passed=True, offset=3,
            reflection_status="rejected",
        ),
        _record("E1-LS1-T4", passed=False, offset=4),
    ):
        replay.persist(record)

    events = EventStore(run_root / "stores" / "events")
    events.record(
        "reflection_completed",
        {
            "task_id": "E1-LS1-T1",
            "same_session_verified": True,
            "session_id": "ses-1",
            "solve_session_id": "ses-1",
            "reflection_session_id": "ses-1",
        },
    )
    events.record(
        "reflection_noop",
        {
            "task_id": "E1-LS1-T2",
            "same_session_verified": True,
            "session_id": "ses-2",
            "solve_session_id": "ses-2",
            "reflection_session_id": "ses-mismatch",
        },
    )
    events.record(
        "reflection_rejected",
        {
            "task_id": "E1-LS1-T3",
            # Equal IDs are insufficient without the explicit host verdict.
            "session_id": "ses-3",
            "solve_session_id": "ses-3",
            "reflection_session_id": "ses-3",
        },
    )
    events.record("reflection_skipped", {"task_id": "E1-LS2-T1"})

    report = ReportGenerator(run_root, config).generate()

    assert report.reflection["n_attempted"] == 3
    assert report.reflection["n_same_session_verified"] == 1
    assert report.reflection["valid_output_rate"] == pytest.approx(2 / 3)
    assert report.reflection["patch_candidate_rate"] == pytest.approx(1 / 3)
    assert report.reflection["noop_rate"] == pytest.approx(1 / 3)
    assert report.reflection["rejection_rate"] == pytest.approx(1 / 3)
    assert "valid_candidate_rate" not in report.reflection
    assert report.reflection_transfer["n_pairs"] == 3
    assert report.reflection_transfer["fail_to_success_count"] == 1
    assert report.reflection_transfer["success_to_fail_count"] == 1
