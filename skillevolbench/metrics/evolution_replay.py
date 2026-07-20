"""Paired original-to-replay metrics for within-environment evolution.

The same T1-T3 task is first attempted while the environment skill library is
still evolving and later replayed against the final frozen library. Pairing the
two attempts separates recovery, regression, and stable outcomes instead of
reporting only an unpaired pass-rate delta.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord


_REPLAY_SUFFIX = "__replay"


@dataclass
class EvolutionReplayReport:
    n_pairs: int = 0
    n_unmatched_replays: int = 0

    original_pass_rate: Optional[float] = None
    replay_pass_rate: Optional[float] = None
    evolution_lift: Optional[float] = None
    mean_reward_lift: Optional[float] = None

    fail_to_success_count: int = 0
    fail_to_fail_count: int = 0
    success_to_success_count: int = 0
    success_to_fail_count: int = 0

    # Conditional probabilities. None means the relevant original-outcome
    # denominator was zero, not a measured rate of zero.
    recovery_rate: Optional[float] = None
    regression_rate: Optional[float] = None
    stable_success_rate: Optional[float] = None
    stable_failure_rate: Optional[float] = None

    per_role: dict[str, dict[str, object]] = field(default_factory=dict)


def _canonical_task_id(task_id: str) -> str:
    return task_id[: -len(_REPLAY_SUFFIX)] if task_id.endswith(_REPLAY_SUFFIX) else task_id


def _summarize_pairs(
    pairs: list[tuple[ReplayRecord, ReplayRecord]],
) -> dict[str, object]:
    n_pairs = len(pairs)
    if not pairs:
        return {
            "n_pairs": 0,
            "original_pass_rate": None,
            "replay_pass_rate": None,
            "evolution_lift": None,
            "mean_reward_lift": None,
            "fail_to_success_count": 0,
            "fail_to_fail_count": 0,
            "success_to_success_count": 0,
            "success_to_fail_count": 0,
            "recovery_rate": None,
            "regression_rate": None,
            "stable_success_rate": None,
            "stable_failure_rate": None,
        }

    fail_to_success = 0
    fail_to_fail = 0
    success_to_success = 0
    success_to_fail = 0
    reward_lift = 0.0
    for original, replay in pairs:
        before = original.outcome.verifier_passed
        after = replay.outcome.verifier_passed
        reward_lift += replay.outcome.reward - original.outcome.reward
        if not before and after:
            fail_to_success += 1
        elif not before and not after:
            fail_to_fail += 1
        elif before and after:
            success_to_success += 1
        else:
            success_to_fail += 1

    original_passes = success_to_success + success_to_fail
    original_failures = fail_to_success + fail_to_fail
    original_pass_rate = original_passes / n_pairs
    replay_pass_rate = (fail_to_success + success_to_success) / n_pairs
    return {
        "n_pairs": n_pairs,
        "original_pass_rate": original_pass_rate,
        "replay_pass_rate": replay_pass_rate,
        "evolution_lift": replay_pass_rate - original_pass_rate,
        "mean_reward_lift": reward_lift / n_pairs,
        "fail_to_success_count": fail_to_success,
        "fail_to_fail_count": fail_to_fail,
        "success_to_success_count": success_to_success,
        "success_to_fail_count": success_to_fail,
        "recovery_rate": (
            fail_to_success / original_failures if original_failures else None
        ),
        "regression_rate": (
            success_to_fail / original_passes if original_passes else None
        ),
        "stable_success_rate": (
            success_to_success / original_passes if original_passes else None
        ),
        "stable_failure_rate": (
            fail_to_fail / original_failures if original_failures else None
        ),
    }


def compute_evolution_replay(
    replay_records: Iterable[ReplayRecord],
) -> EvolutionReplayReport:
    """Pair ``primary`` and ``within_env_replay`` records by task id."""
    records = list(replay_records)
    originals = {
        record.task_id: record
        for record in records
        if getattr(record, "replay_mode", "primary") == "primary"
    }
    replay_records_only = [
        record
        for record in records
        if getattr(record, "replay_mode", "primary") == "within_env_replay"
    ]

    pairs: list[tuple[ReplayRecord, ReplayRecord]] = []
    unmatched = 0
    for replay in replay_records_only:
        original = originals.get(_canonical_task_id(replay.task_id))
        if original is None:
            unmatched += 1
            continue
        pairs.append((original, replay))

    summary = _summarize_pairs(pairs)
    per_role: dict[str, dict[str, object]] = {}
    for role in sorted({original.task_role for original, _ in pairs}):
        per_role[role] = _summarize_pairs(
            [pair for pair in pairs if pair[0].task_role == role]
        )

    return EvolutionReplayReport(
        n_pairs=int(summary["n_pairs"]),
        n_unmatched_replays=unmatched,
        original_pass_rate=summary["original_pass_rate"],
        replay_pass_rate=summary["replay_pass_rate"],
        evolution_lift=summary["evolution_lift"],
        mean_reward_lift=summary["mean_reward_lift"],
        fail_to_success_count=int(summary["fail_to_success_count"]),
        fail_to_fail_count=int(summary["fail_to_fail_count"]),
        success_to_success_count=int(summary["success_to_success_count"]),
        success_to_fail_count=int(summary["success_to_fail_count"]),
        recovery_rate=summary["recovery_rate"],
        regression_rate=summary["regression_rate"],
        stable_success_rate=summary["stable_success_rate"],
        stable_failure_rate=summary["stable_failure_rate"],
        per_role=per_role,
    )


__all__ = ["EvolutionReplayReport", "compute_evolution_replay"]
