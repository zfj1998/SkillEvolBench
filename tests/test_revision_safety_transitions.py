from __future__ import annotations

from datetime import datetime, timedelta, timezone

from skillevolbench.metrics.revision_safety import compute_revision_safety
from skillevolbench.schemas import ReplayRecord, TrialOutcome


def _record(task_id: str, *, passed: bool, offset: int) -> ReplayRecord:
    role_by_tier = {
        "T1": "canonical",
        "T2": "enriched",
        "T3": "variant",
        "T4": "context-shift",
    }
    tier = task_id.rsplit("-", 1)[-1]
    return ReplayRecord(
        task_id=task_id,
        family_id="-".join(task_id.split("-")[:2]),
        env_id=task_id.split("-", 1)[0],
        task_role=role_by_tier[tier],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc)
        + timedelta(seconds=offset),
        outcome=TrialOutcome(task_id=task_id, verifier_passed=passed),
    )


def test_applied_revisions_report_cross_task_outcome_flips() -> None:
    records = [
        _record("E1-LS1-T1", passed=False, offset=1),
        _record("E1-LS1-T2", passed=True, offset=2),
        _record("E1-LS1-T3", passed=False, offset=3),
        _record("E1-LS1-T4", passed=False, offset=4),
    ]
    events = [
        {"event_type": "patch_applied", "triggered_by_task": "E1-LS1-T1"},
        {"event_type": "patch_applied", "triggered_by_task": "E1-LS1-T2"},
        {"event_type": "patch_applied", "triggered_by_task": "E1-LS1-T3"},
    ]

    report = compute_revision_safety(
        patch_events=events,
        replay_records=records,
    )

    assert report.n_cross_task_revision_pairs == 3
    assert report.fail_to_success_count == 1
    assert report.success_to_fail_count == 1
    assert report.fail_to_fail_count == 1
    assert report.success_to_success_count == 0
    assert report.failure_recovery_rate == 0.5
    assert report.success_regression_rate == 1.0


def test_transition_pairs_deduplicate_patch_events_per_trigger() -> None:
    records = [
        _record("E1-LS1-T1", passed=True, offset=1),
        _record("E1-LS1-T2", passed=True, offset=2),
    ]
    duplicate = {
        "event_type": "patch_applied",
        "triggered_by_task": "E1-LS1-T1",
    }

    report = compute_revision_safety(
        patch_events=[duplicate, dict(duplicate)],
        replay_records=records,
    )

    assert report.n_applied == 2
    assert report.n_cross_task_revision_pairs == 1
    assert report.success_to_success_count == 1
