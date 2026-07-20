"""Revision-safety metrics.

Captures whether strategy revisions help or hurt later same-family trials.
Computed entirely from EventStore (patches.jsonl) and ReplayStore.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord


@dataclass
class RevisionSafetyReport:
    """Revision safety counters and rates."""

    n_proposed: int = 0
    n_applied: int = 0
    n_rejected: int = 0
    n_rollbacks: int = 0
    n_no_change: int = 0  # applied patches whose upserts didn't change content

    # Rates
    revision_acceptance_rate: float = 0.0      # applied / proposed
    rollback_rate: float = 0.0                 # rollbacks / proposed
    no_change_revision_rate: float = 0.0       # no_change / applied

    # Help / hurt: did the next same-family task improve / regress?
    revision_help_rate: float = 0.0
    revision_hurt_rate: float = 0.0

    # Outcome transition after an applied revision, paired to the next
    # *different* task in the same family. These are the direct diagnostic
    # for failure-summary recovery and success-summary regression. They are
    # observational unless compared against a no-revision control because
    # the two tasks intentionally use different inputs and may differ in
    # difficulty.
    n_cross_task_revision_pairs: int = 0
    fail_to_success_count: int = 0
    fail_to_fail_count: int = 0
    success_to_success_count: int = 0
    success_to_fail_count: int = 0
    failure_recovery_rate: Optional[float] = None
    success_regression_rate: Optional[float] = None

    # Patch overfitting: revision fixes T2/T3 fail but T4-T6 of same family later regress.
    patch_overfitting_rate: float = 0.0

    # Per-strategy breakdown
    by_strategy_acceptance: dict[str, float] = field(default_factory=dict)


def compute_revision_safety(
    *,
    patch_events: Iterable[dict],
    replay_records: Iterable[ReplayRecord],
) -> RevisionSafetyReport:
    """Aggregate from EventStore patch events + ReplayStore records.

    Parameters
    ----------
    patch_events
        ``EventStore.all_events(channel="patches")`` output -- a list of
        dict events. We filter by event_type internally.
    replay_records
        ``replay_store.all_records()``.
    """
    events = list(patch_events)
    records = list(replay_records)

    proposed = [e for e in events if e.get("event_type") == "patch_proposed"]
    applied = [e for e in events if e.get("event_type") == "patch_applied"]
    rejected = [e for e in events if e.get("event_type") == "patch_rejected"]
    rollbacks = [e for e in events if e.get("event_type") == "rollback_decision"]

    rep = RevisionSafetyReport(
        n_proposed=len(proposed),
        n_applied=len(applied),
        n_rejected=len(rejected),
        n_rollbacks=len(rollbacks),
    )
    if proposed:
        rep.revision_acceptance_rate = len(applied) / len(proposed)
        rep.rollback_rate = len(rollbacks) / len(proposed)

    # No-change revisions: applied patches with no upsert + no delete.
    no_change_count = sum(
        1 for e in applied
        if not e.get("upsert_paths") and not e.get("delete_paths")
    )
    rep.n_no_change = no_change_count
    if applied:
        rep.no_change_revision_rate = no_change_count / len(applied)

    # Per-strategy acceptance rates
    by_strat_proposed: dict[str, int] = defaultdict(int)
    by_strat_applied: dict[str, int] = defaultdict(int)
    for e in proposed:
        by_strat_proposed[e.get("strategy", "?")] += 1
    for e in applied:
        by_strat_applied[e.get("strategy", "?")] += 1
    for s, p in by_strat_proposed.items():
        rep.by_strategy_acceptance[s] = (
            by_strat_applied.get(s, 0) / p if p else 0.0
        )

    # Help / hurt: walk the records ordered by timestamp; for each applied
    # patch (triggered_by_task), compare verifier_passed of the *next*
    # same-family task vs its predecessor.
    rep.revision_help_rate, rep.revision_hurt_rate = _help_hurt(applied, records)

    transitions = _cross_task_transitions(applied, records)
    for field_name, value in transitions.items():
        setattr(rep, field_name, value)

    # Patch overfitting: revision triggered by a T2/T3 fail; check if any
    # T4-T6 of the same family later fail.
    rep.patch_overfitting_rate = _patch_overfitting(applied, records)

    return rep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _help_hurt(
    applied: list[dict], records: Iterable[ReplayRecord]
) -> tuple[float, float]:
    """Match each apply_patch event to the *next* same-family record.
    Compute help_rate (next passed) / hurt_rate (next failed).
    """
    records_sorted = sorted(records, key=lambda r: r.timestamp)
    if not applied or not records_sorted:
        return 0.0, 0.0

    # Build (family_id, sorted records) index.
    by_family: dict[str, list[ReplayRecord]] = defaultdict(list)
    for r in records_sorted:
        by_family[r.family_id].append(r)

    helped = 0
    hurt = 0
    counted = 0
    for ev in applied:
        triggered = ev.get("triggered_by_task", "")
        if not triggered:
            continue
        family_id = "-".join(triggered.split("-")[:2])  # E1-LS1-T2 -> E1-LS1
        family = by_family.get(family_id, [])
        # Find the trigger record by task_id, then the next record AFTER.
        try:
            idx = next(i for i, r in enumerate(family) if r.task_id == triggered)
        except StopIteration:
            continue
        if idx + 1 >= len(family):
            continue
        nxt = family[idx + 1]
        counted += 1
        if nxt.outcome.verifier_passed:
            helped += 1
        else:
            hurt += 1
    if counted == 0:
        return 0.0, 0.0
    return helped / counted, hurt / counted


def _patch_overfitting(
    applied: list[dict], records: Iterable[ReplayRecord]
) -> float:
    """For each revision triggered by a T2/T3 failure, did any later
    T4-T6 of the *same family* fail?

    Numerator: applied patches whose family later had at least one eval
    fail. Denominator: applied patches.
    """
    records_sorted = sorted(records, key=lambda r: r.timestamp)
    if not applied:
        return 0.0
    by_family: dict[str, list[ReplayRecord]] = defaultdict(list)
    for r in records_sorted:
        by_family[r.family_id].append(r)

    overfit = 0
    counted = 0
    for ev in applied:
        triggered = ev.get("triggered_by_task", "")
        if not triggered:
            continue
        family_id = "-".join(triggered.split("-")[:2])
        family = by_family.get(family_id, [])
        try:
            idx = next(i for i, r in enumerate(family) if r.task_id == triggered)
        except StopIteration:
            continue
        # Look only at records *after* the trigger AND eval-block roles.
        future = family[idx + 1:]
        eval_records = [
            r for r in future
            if r.task_role in {"context-shift", "adversarial", "composition"}
        ]
        if not eval_records:
            continue
        counted += 1
        if any(not r.outcome.verifier_passed for r in eval_records):
            overfit += 1
    if counted == 0:
        return 0.0
    return overfit / counted


def _cross_task_transitions(
    applied: list[dict], records: Iterable[ReplayRecord]
) -> dict[str, int | float | None]:
    """Pair each revised task with the next distinct same-family task.

    A task may emit more than one low-level ``patch_applied`` event. Such
    events represent one post-task revision boundary for this diagnostic, so
    ``triggered_by_task`` is de-duplicated before pairing.
    """
    records_sorted = sorted(records, key=lambda record: record.timestamp)
    by_family: dict[str, list[ReplayRecord]] = defaultdict(list)
    for record in records_sorted:
        by_family[record.family_id].append(record)

    counts = {
        "fail_to_success_count": 0,
        "fail_to_fail_count": 0,
        "success_to_success_count": 0,
        "success_to_fail_count": 0,
    }
    seen_triggers: set[str] = set()
    n_pairs = 0
    for event in applied:
        triggered = event.get("triggered_by_task", "")
        if not triggered or triggered in seen_triggers:
            continue
        seen_triggers.add(triggered)
        family_id = "-".join(triggered.split("-")[:2])
        family = by_family.get(family_id, [])
        try:
            index = next(
                i for i, record in enumerate(family)
                if record.task_id == triggered
            )
        except StopIteration:
            continue
        if index + 1 >= len(family):
            continue

        before = family[index].outcome.verifier_passed
        after = family[index + 1].outcome.verifier_passed
        if not before and after:
            counts["fail_to_success_count"] += 1
        elif not before and not after:
            counts["fail_to_fail_count"] += 1
        elif before and after:
            counts["success_to_success_count"] += 1
        else:
            counts["success_to_fail_count"] += 1
        n_pairs += 1

    n_failure = counts["fail_to_success_count"] + counts["fail_to_fail_count"]
    n_success = counts["success_to_success_count"] + counts["success_to_fail_count"]
    return {
        "n_cross_task_revision_pairs": n_pairs,
        **counts,
        "failure_recovery_rate": (
            counts["fail_to_success_count"] / n_failure if n_failure else None
        ),
        "success_regression_rate": (
            counts["success_to_fail_count"] / n_success if n_success else None
        ),
    }


__all__ = ["RevisionSafetyReport", "compute_revision_safety"]
