"""Cross-task outcome transitions after same-session reflection.

Unlike :mod:`revision_safety`, this metric does not condition on a patch being
applied.  Every terminal reflection outcome is part of the model behaviour we
want to measure: a valid patch, a valid no-op, a rejected candidate, or an
intentional skip.  The source trial is paired with the next *different*
primary task in the same family, so the report measures transfer to a new
input rather than an immediate replay of the same task.

These transitions are observational.  Consecutive tasks intentionally differ
in input and may differ in difficulty, so causal claims still require a
matched no-reflection control.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord


REFLECTION_STATUSES = ("completed", "noop", "rejected", "skipped")


@dataclass
class ReflectionTransitionCounts:
    """Outcome-transition counts and conditional rates."""

    n_pairs: int = 0
    fail_to_success_count: int = 0
    fail_to_fail_count: int = 0
    success_to_success_count: int = 0
    success_to_fail_count: int = 0
    failure_recovery_rate: Optional[float] = None
    success_regression_rate: Optional[float] = None


@dataclass
class ReflectionTransitionPair:
    """One auditable source-reflection to next-task pairing."""

    family_id: str
    source_task_id: str
    next_task_id: str
    reflection_status: str
    source_passed: bool
    next_passed: bool
    transition: str


@dataclass
class ReflectionTransferReport(ReflectionTransitionCounts):
    """Pooled and reflection-status-stratified transfer report."""

    by_reflection_status: dict[str, ReflectionTransitionCounts] = field(
        default_factory=dict
    )
    pairs: list[ReflectionTransitionPair] = field(default_factory=list)


def _transition(source_passed: bool, next_passed: bool) -> str:
    if not source_passed and next_passed:
        return "fail_to_success"
    if not source_passed and not next_passed:
        return "fail_to_fail"
    if source_passed and next_passed:
        return "success_to_success"
    return "success_to_fail"


def _add_pair(counts: ReflectionTransitionCounts, transition: str) -> None:
    field_name = f"{transition}_count"
    setattr(counts, field_name, getattr(counts, field_name) + 1)
    counts.n_pairs += 1


def _finalize_rates(counts: ReflectionTransitionCounts) -> None:
    n_failure_sources = (
        counts.fail_to_success_count + counts.fail_to_fail_count
    )
    n_success_sources = (
        counts.success_to_success_count + counts.success_to_fail_count
    )
    counts.failure_recovery_rate = (
        counts.fail_to_success_count / n_failure_sources
        if n_failure_sources
        else None
    )
    counts.success_regression_rate = (
        counts.success_to_fail_count / n_success_sources
        if n_success_sources
        else None
    )


def compute_reflection_transfer(
    replay_records: Iterable[ReplayRecord],
) -> ReflectionTransferReport:
    """Pair each reflected primary task with its next different family task.

    Only records whose source ``reflection.status`` is one of
    :data:`REFLECTION_STATUSES` contribute a pair.  Filtering primary records
    here (as well as in ``ReportGenerator``) prevents within-environment replay
    and T6 oracle-shadow trials from becoming accidental transfer targets.
    """

    records = sorted(
        (
            record
            for record in replay_records
            if getattr(record, "replay_mode", "primary") == "primary"
        ),
        key=lambda record: record.timestamp,
    )
    by_family: dict[str, list[ReplayRecord]] = defaultdict(list)
    for record in records:
        by_family[record.family_id].append(record)

    report = ReflectionTransferReport(
        by_reflection_status={
            status: ReflectionTransitionCounts()
            for status in REFLECTION_STATUSES
        }
    )
    seen_source_tasks: set[str] = set()

    for family_id, family_records in by_family.items():
        for source_index, source in enumerate(family_records):
            # Defensive de-duplication for hand-built/legacy record lists.
            # ReplayStore normally enforces one row per task_id.
            if source.task_id in seen_source_tasks:
                continue
            seen_source_tasks.add(source.task_id)

            status = source.reflection.get("status")
            if status not in REFLECTION_STATUSES:
                continue

            next_record = next(
                (
                    candidate
                    for candidate in family_records[source_index + 1 :]
                    if candidate.task_id != source.task_id
                ),
                None,
            )
            if next_record is None:
                continue

            source_passed = bool(source.outcome.verifier_passed)
            next_passed = bool(next_record.outcome.verifier_passed)
            transition = _transition(source_passed, next_passed)
            _add_pair(report, transition)
            _add_pair(report.by_reflection_status[status], transition)
            report.pairs.append(
                ReflectionTransitionPair(
                    family_id=family_id,
                    source_task_id=source.task_id,
                    next_task_id=next_record.task_id,
                    reflection_status=status,
                    source_passed=source_passed,
                    next_passed=next_passed,
                    transition=transition,
                )
            )

    _finalize_rates(report)
    for counts in report.by_reflection_status.values():
        _finalize_rates(counts)
    return report


__all__ = [
    "REFLECTION_STATUSES",
    "ReflectionTransitionCounts",
    "ReflectionTransitionPair",
    "ReflectionTransferReport",
    "compute_reflection_transfer",
]
