"""Library-health metrics (Part 10 §12.5).

Captures whether the lifelong skill library is **growing, consolidating, or
rotting** over the run.

Computed from:

* ``library/manifest.yaml`` (status counts + version histories)
* ``EventStore`` (patch_applied / proposed / rejected)
* ``ReplayStore`` (skills_actually_used aggregate)
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord, SkillManifestEntry, SkillStatus


# Threshold used to define "harmful" skill at metric time. Conservative;
# matches LifecycleMaintainer's default retire_harm_threshold.
_HARM_THRESHOLD: float = 0.7
_MIN_USES_FOR_HARM: int = 3


@dataclass
class LibraryHealthReport:
    """All Part 10 §12.5 fields."""

    # Counts
    total_skill_count: int = 0
    active_skill_count: int = 0
    quarantined_skill_count: int = 0
    retired_skill_count: int = 0

    # Effective: skills that were actually used in eval-block records.
    effective_skill_count: int = 0

    # Inflation: final_skill_count / tasks_attempted.
    skill_inflation_rate: float = 0.0

    # Consolidation: revisions / creations (>1 = mostly revising; <1 = mostly creating).
    consolidation_ratio: float = 0.0

    # Stale rate: active skills never used / total active.
    stale_rate: float = 0.0

    # Redundancy / conflict (heuristic, see compute fn).
    redundancy_rate: float = 0.0
    conflict_count: int = 0

    # Harmful retention.
    harmful_skill_count: int = 0
    harmful_retained_count: int = 0
    harmful_retention_rate: float = 0.0

    # Retirement quality.
    retirement_count: int = 0
    retirement_precision: Optional[float] = None  # None when no retirements happened
    retirement_recall: Optional[float] = None

    # Lifecycle activity
    n_patches_applied: int = 0
    n_patches_rejected: int = 0
    n_patches_proposed: int = 0
    library_churn_rate: float = 0.0  # lifecycle events / task

    # Per-skill audit (for analysis)
    per_skill_use_count: dict[str, int] = field(default_factory=dict)
    per_skill_failure_rate: dict[str, float] = field(default_factory=dict)


def compute_library_health(
    *,
    manifest_skills: Iterable[SkillManifestEntry],
    replay_records: Iterable[ReplayRecord],
    event_counts: dict[str, int],
    n_tasks_attempted: int,
) -> LibraryHealthReport:
    """Aggregate library state + replay history into a health report.

    Parameters
    ----------
    manifest_skills
        Iterable from ``library.list_all()`` (or ``[]`` for control baselines).
    replay_records
        All replay records from ``replay_store.all_records()``.
    event_counts
        ``{event_type: n_events}`` map. Use
        ``event_store.events_of_type(...)`` for the relevant types and pass
        in lengths.
    n_tasks_attempted
        Denominator for inflation + churn rates. Pass the number of trials
        that actually executed (not necessarily 180 for partial runs).
    """
    skills = list(manifest_skills)
    records = list(replay_records)

    rep = LibraryHealthReport()
    rep.total_skill_count = len(skills)
    rep.active_skill_count = sum(1 for s in skills if s.status == SkillStatus.ACTIVE)
    rep.quarantined_skill_count = sum(
        1 for s in skills if s.status == SkillStatus.QUARANTINED
    )
    rep.retired_skill_count = sum(
        1 for s in skills if s.status == SkillStatus.RETIRED
    )

    # Per-skill use + failure aggregates.
    use_counter: Counter[str] = Counter()
    fail_counter: Counter[str] = Counter()
    eval_use: set[str] = set()
    for r in records:
        for sid in r.skills_actually_used:
            use_counter[sid] += 1
            if not r.outcome.verifier_passed:
                fail_counter[sid] += 1
            if r.task_role in {"context-shift", "adversarial", "composition"}:
                eval_use.add(sid)
    rep.effective_skill_count = len(eval_use & {s.skill_id for s in skills})

    rep.per_skill_use_count = dict(use_counter)
    rep.per_skill_failure_rate = {
        sid: (fail_counter[sid] / use_counter[sid]) if use_counter[sid] else 0.0
        for sid in use_counter
    }

    # Inflation
    if n_tasks_attempted > 0:
        rep.skill_inflation_rate = rep.total_skill_count / n_tasks_attempted

    # Consolidation: count CREATE operations vs REVISE operations from
    # manifest version histories.
    n_creates = 0
    n_revises = 0
    n_retire_ops = 0
    for s in skills:
        if not s.versions:
            continue
        v0 = s.versions[0]
        # author_strategy == curated_seed counts as 1 creation;
        # zero_shot / induction also count.
        n_creates += 1
        n_revises += max(0, len(s.versions) - 1)
        if s.status == SkillStatus.RETIRED:
            n_retire_ops += 1
    if n_creates > 0:
        rep.consolidation_ratio = n_revises / n_creates

    # Stale: active skills never used.
    active_ids = {s.skill_id for s in skills if s.status == SkillStatus.ACTIVE}
    used_ids = set(use_counter)
    if active_ids:
        stale = active_ids - used_ids
        rep.stale_rate = len(stale) / len(active_ids)

    # Redundancy + conflict (heuristic)
    rep.redundancy_rate, rep.conflict_count = _redundancy_and_conflict(skills)

    # Harmful retention
    harmful_ids = _harmful_set(use_counter, fail_counter)
    rep.harmful_skill_count = len(harmful_ids)
    retained_harmful = harmful_ids & active_ids
    rep.harmful_retained_count = len(retained_harmful)
    if rep.harmful_skill_count > 0:
        rep.harmful_retention_rate = (
            rep.harmful_retained_count / rep.harmful_skill_count
        )

    # Retirement quality
    rep.retirement_count = n_retire_ops
    retired_ids = {s.skill_id for s in skills if s.status == SkillStatus.RETIRED}
    if rep.retirement_count > 0:
        truly_harmful_retired = harmful_ids & retired_ids
        rep.retirement_precision = (
            len(truly_harmful_retired) / rep.retirement_count
        )
    if rep.harmful_skill_count > 0:
        retired_harmful = harmful_ids & retired_ids
        rep.retirement_recall = (
            len(retired_harmful) / rep.harmful_skill_count
        )

    # Lifecycle activity
    rep.n_patches_applied = int(event_counts.get("patch_applied", 0))
    rep.n_patches_rejected = int(event_counts.get("patch_rejected", 0))
    rep.n_patches_proposed = int(event_counts.get("patch_proposed", 0))
    if n_tasks_attempted > 0:
        rep.library_churn_rate = (
            rep.n_patches_applied + rep.n_patches_rejected
        ) / n_tasks_attempted
    return rep


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _harmful_set(
    use_counter: Counter[str], fail_counter: Counter[str]
) -> set[str]:
    """Skills with use_count >= MIN and failure_rate >= HARM_THRESHOLD."""
    harmful: set[str] = set()
    for sid, uses in use_counter.items():
        if uses < _MIN_USES_FOR_HARM:
            continue
        if (fail_counter[sid] / uses) >= _HARM_THRESHOLD:
            harmful.add(sid)
    return harmful


def _redundancy_and_conflict(
    skills: list[SkillManifestEntry],
) -> tuple[float, int]:
    """Heuristic redundancy + conflict counts.

    Redundancy: pairs of active skills in the same family with overlapping
    ``applicability.include`` tags (or both empty).

    Conflict: pairs of active skills where one's ``applicability.exclude``
    contains a tag in the other's ``applicability.include`` (or vice
    versa).

    These heuristics are coarse; they exist to flag obviously broken
    libraries. The Part 10 paper figure should pair them with manual review.
    """
    actives = [s for s in skills if s.status == SkillStatus.ACTIVE]
    n = len(actives)
    if n < 2:
        return 0.0, 0
    redundant_pairs = 0
    conflict_pairs = 0
    for i in range(n):
        for j in range(i + 1, n):
            a, b = actives[i], actives[j]
            if a.family_id == b.family_id:
                a_inc = set(a.applicability.include)
                b_inc = set(b.applicability.include)
                if a_inc and b_inc and (a_inc & b_inc):
                    redundant_pairs += 1
                elif not a_inc and not b_inc:
                    redundant_pairs += 1
            a_inc = set(a.applicability.include)
            b_exc = set(b.applicability.exclude)
            b_inc = set(b.applicability.include)
            a_exc = set(a.applicability.exclude)
            if (a_inc & b_exc) or (b_inc & a_exc):
                conflict_pairs += 1
    total_pairs = n * (n - 1) / 2
    redundancy_rate = redundant_pairs / total_pairs if total_pairs else 0.0
    return redundancy_rate, conflict_pairs


__all__ = ["LibraryHealthReport", "compute_library_health"]
