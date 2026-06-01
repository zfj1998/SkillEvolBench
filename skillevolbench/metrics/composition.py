"""T6 composition metrics (Part 10 §12.4).

The signature paper test. T6 fail can come from:

1. Required prerequisite skill not learned
2. Skill exists but wasn't retrieved
3. Retrieval got it but ordering is wrong
4. Ordering correct but execution failed
5. Skill quality issue
6. Conflict between retrieved skills
7. Shortcut bypass
8. Integration failure (skills work alone but not composed)

This module classifies T6 failures into the 8-category taxonomy. We compute
the **Required Skill Hit Rate** and the **Retrieval-Composition Gap**
(Oracle - Learned) when an oracle-condition rerun is available; otherwise
we surface only the Learned condition.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord, RetrievalEvent, TaskRole


@dataclass
class T6FailureTaxonomy:
    """Counts of T6 failures by category."""

    missing_prerequisite: int = 0       # required skill never created in library
    retrieval_failure: int = 0          # skill exists but wasn't retrieved
    ordering_failure: int = 0           # all retrieved but task still failed (best guess)
    application_failure: int = 0        # process_passed=False; agent didn't follow the procedure
    skill_quality_failure: int = 0      # retrieved + applied but verifier failed (skill content bad)
    shortcut_failure: int = 0           # outcome passed but process failed
    unclassified: int = 0


@dataclass
class T6CompositionReport:
    n_t6: int = 0
    t6_pass_rate: float = 0.0
    required_skill_hit_rate: float = 0.0
    composition_ordering_accuracy: float = 0.0

    # Oracle-shadow vs learned retrieval.
    learned_t6_pass_rate: Optional[float] = None
    oracle_t6_pass_rate: Optional[float] = None
    retrieval_composition_gap: Optional[float] = None

    failure_taxonomy: T6FailureTaxonomy = field(default_factory=T6FailureTaxonomy)
    per_task: list[dict] = field(default_factory=list)


def compute_t6_composition(
    *,
    replay_records: Iterable[ReplayRecord],
    retrieval_events: Iterable[RetrievalEvent],
    library_skill_ids: set[str],
    task_specs: dict[str, list[str]],  # task_id -> required_skills (T6 only)
    task_compose_orders: dict[str, list[str]],  # task_id -> required_skill_compose_order
    oracle_records: Optional[Iterable[ReplayRecord]] = None,
) -> T6CompositionReport:
    """Aggregate T6 records into composition metrics.

    Parameters
    ----------
    replay_records
        All replay records from the run.
    retrieval_events
        All retrieval events for the run.
    library_skill_ids
        Set of skill ids that exist (active OR retired) in the library at
        the time of the eval. Used to decide "missing_prerequisite" vs
        "retrieval_failure".
    task_specs / task_compose_orders
        Maps from ``TaskRegistry`` -- needed because ``ReplayRecord`` only
        stores task_id, not the static T6 ground truth.
    oracle_records
        Optional shadow records under oracle retrieval. When
        present, populates oracle_t6_pass_rate + retrieval_composition_gap.
    """
    records = [r for r in replay_records if r.task_role == TaskRole.COMPOSITION.value]
    rep = T6CompositionReport(n_t6=len(records))
    if not records:
        return rep

    rep.t6_pass_rate = sum(1 for r in records if r.outcome.verifier_passed) / len(records)
    rep.learned_t6_pass_rate = rep.t6_pass_rate

    # Index retrieval events by task_id (last event per task wins).
    retr_by_task: dict[str, RetrievalEvent] = {}
    for e in retrieval_events:
        retr_by_task[e.task_id] = e

    # Required-skill hits + ordering + failure classification.
    n_hits = 0
    n_ordering_correct = 0
    taxonomy = T6FailureTaxonomy()

    for r in records:
        spec_required = set(task_specs.get(r.task_id, []))
        spec_order = list(task_compose_orders.get(r.task_id, []))
        retrieval = retr_by_task.get(r.task_id)
        retrieved = set(retrieval.retrieved_skill_ids) if retrieval else set()
        actually_used = list(r.skills_actually_used)

        # Hit rate
        if spec_required and spec_required.issubset(retrieved):
            n_hits += 1

        # Ordering accuracy: actually-used must respect the required order.
        if spec_order and _follows_order(actually_used, spec_order):
            n_ordering_correct += 1

        # Failure classification (only on failed records)
        if r.outcome.verifier_passed:
            continue

        # Missing prerequisite: at least one required skill not in library.
        if spec_required and not spec_required.issubset(library_skill_ids):
            taxonomy.missing_prerequisite += 1
            continue

        # Retrieval failure: required skills exist but not all retrieved.
        if spec_required and not spec_required.issubset(retrieved):
            taxonomy.retrieval_failure += 1
            continue

        # Shortcut: outcome passed but process failed (or vice-versa).
        if r.outcome.outcome_passed and r.outcome.process_passed is False:
            taxonomy.shortcut_failure += 1
            continue

        # Application failure: process_passed False (agent didn't follow procedure).
        if r.outcome.process_passed is False:
            taxonomy.application_failure += 1
            continue

        # Ordering failure: retrieved everything but order was wrong.
        if spec_order and not _follows_order(actually_used, spec_order):
            taxonomy.ordering_failure += 1
            continue

        # Skill quality: all good, just bad SKILL.md content.
        taxonomy.skill_quality_failure += 1

    rep.required_skill_hit_rate = n_hits / len(records)
    rep.composition_ordering_accuracy = n_ordering_correct / len(records)
    rep.failure_taxonomy = taxonomy

    # Oracle vs Learned gap
    if oracle_records is not None:
        oracle_list = [
            r for r in oracle_records
            if r.task_role == TaskRole.COMPOSITION.value
        ]
        if oracle_list:
            oracle_pass = sum(
                1 for r in oracle_list if r.outcome.verifier_passed
            ) / len(oracle_list)
            rep.oracle_t6_pass_rate = oracle_pass
            rep.retrieval_composition_gap = oracle_pass - rep.learned_t6_pass_rate

    # Per-task audit (small slice for analysis CSVs)
    rep.per_task = [
        {
            "task_id": r.task_id,
            "verifier_passed": r.outcome.verifier_passed,
            "required_hit": (
                set(task_specs.get(r.task_id, [])).issubset(
                    set(retr_by_task.get(r.task_id, RetrievalEvent(task_id=r.task_id)).retrieved_skill_ids)
                )
                if r.task_id in retr_by_task else False
            ),
        }
        for r in records
    ]
    return rep


def _follows_order(actually_used: list[str], required_order: list[str]) -> bool:
    """True iff ``required_order`` appears as an in-order subsequence of
    ``actually_used``. Allows interleaved unrelated skills."""
    if not required_order:
        return True
    iter_used = iter(actually_used)
    for req in required_order:
        for u in iter_used:
            if u == req:
                break
        else:
            return False
    return True


__all__ = [
    "T6FailureTaxonomy",
    "T6CompositionReport",
    "compute_t6_composition",
]
