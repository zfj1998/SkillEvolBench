from __future__ import annotations

import pytest

from skillevolbench.metrics.evolution_replay import compute_evolution_replay
from skillevolbench.schemas import ReplayRecord, TrialOutcome


def _record(
    task_id: str,
    *,
    passed: bool,
    reward: float,
    mode: str = "primary",
    role: str = "canonical",
) -> ReplayRecord:
    canonical_id = task_id.removesuffix("__replay")
    return ReplayRecord(
        task_id=task_id,
        family_id="E1-LS1",
        env_id="E1",
        task_role=role,
        replay_mode=mode,
        outcome=TrialOutcome(
            task_id=canonical_id,
            verifier_passed=passed,
            reward=reward,
        ),
    )


def test_paired_replay_reports_recovery_and_regression() -> None:
    records = [
        _record("E1-LS1-T1", passed=False, reward=0.1),
        _record("E1-LS1-T2", passed=False, reward=0.2, role="enriched"),
        _record("E1-LS1-T3", passed=True, reward=1.0, role="variant"),
        _record("E1-LS2-T1", passed=True, reward=1.0),
        _record(
            "E1-LS1-T1__replay",
            passed=True,
            reward=1.0,
            mode="within_env_replay",
        ),
        _record(
            "E1-LS1-T2__replay",
            passed=False,
            reward=0.3,
            mode="within_env_replay",
            role="enriched",
        ),
        _record(
            "E1-LS1-T3__replay",
            passed=True,
            reward=1.0,
            mode="within_env_replay",
            role="variant",
        ),
        _record(
            "E1-LS2-T1__replay",
            passed=False,
            reward=0.0,
            mode="within_env_replay",
        ),
    ]

    report = compute_evolution_replay(records)

    assert report.n_pairs == 4
    assert report.fail_to_success_count == 1
    assert report.fail_to_fail_count == 1
    assert report.success_to_success_count == 1
    assert report.success_to_fail_count == 1
    assert report.original_pass_rate == 0.5
    assert report.replay_pass_rate == 0.5
    assert report.evolution_lift == 0.0
    assert report.recovery_rate == 0.5
    assert report.regression_rate == 0.5
    assert report.mean_reward_lift == pytest.approx(0.0)
    assert report.per_role["canonical"]["n_pairs"] == 2


def test_unmatched_replay_is_reported_not_silently_paired() -> None:
    report = compute_evolution_replay(
        [
            _record(
                "E1-LS5-T3__replay",
                passed=True,
                reward=1.0,
                mode="within_env_replay",
            )
        ]
    )

    assert report.n_pairs == 0
    assert report.n_unmatched_replays == 1
    assert report.evolution_lift is None
