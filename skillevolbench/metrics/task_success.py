"""Task-success metrics (Part 10 §12.1).

Per-role pass rates, plus T5 process-correct (trap resistance) and three
aggregates: Learning SR / Evaluation SR / Overall SR.

The T5 ``trap_resistance`` metric is *tighter* than the basic T5 pass rate:
it requires both ``outcome_passed`` AND ``process_passed`` so that hidden
tests catching shortcut fixes (Part 1 §1.6) actually weigh on the score.
A baseline that hardcodes ``if region == "CA":`` would pass enough outcome
tests to look healthy but fails the process check -- trap resistance
captures that.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord, TaskRole


_LEARNING_ROLES = frozenset({
    TaskRole.CANONICAL.value,
    TaskRole.ENRICHED.value,
    TaskRole.VARIANT.value,
})
_EVAL_ROLES = frozenset({
    TaskRole.CONTEXT_SHIFT.value,
    TaskRole.ADVERSARIAL.value,
    TaskRole.COMPOSITION.value,
})


@dataclass
class TaskSuccessReport:
    """Comprehensive per-role + aggregate success report."""

    # Per-role pass rates (verifier_passed)
    t1_pass_rate: float = 0.0
    t2_pass_rate: float = 0.0
    t3_pass_rate: float = 0.0
    t4_transfer: float = 0.0
    t5_pass_rate: float = 0.0
    t5_trap_resistance: float = 0.0
    t6_composition_rate: float = 0.0

    # Aggregates
    learning_sr: float = 0.0          # mean of T1+T2+T3 (mixes no-skill T1 for selfgen)
    learning_sr_t2_t3: float = 0.0    # mean of T2+T3 only -- fair "with-skill" cross-baseline measure
    evaluation_sr: float = 0.0        # mean of T4+T5+T6 (frozen library; canonical headline)
    overall_sr: float = 0.0           # mean of T1..T6

    # Dual-T6 retrieval ablation (only populated when ``baseline.dual_t6_retrieval`` is True
    # and the run produced shadow trials). Shadow trials use OracleRetriever
    # over the SAME (frozen) library as their paired primary T6, so the
    # uplift below is a paired retrieval-only delta.
    t6_oracle_pass_rate: Optional[float] = None
    t6_oracle_uplift: Optional[float] = None
    n_t6_oracle_shadow_trials: int = 0

    # Per-role record counts (for confidence reporting)
    n_per_role: dict[str, int] = field(default_factory=dict)


def compute_task_success(records: Iterable[ReplayRecord]) -> TaskSuccessReport:
    """Aggregate a list of :class:`ReplayRecord` into a TaskSuccessReport.

    Empty input is OK -- all rates default to 0.0. Records whose
    ``outcome.process_passed`` is ``None`` (e.g. E5/E6 tasks that don't
    write a process_report.json) fall back to ``verifier_passed`` for the
    trap-resistance numerator.

    Dual-T6 shadow trials (``replay_mode == "shadow_oracle"``) are
    EXCLUDED from all the headline metrics (per-role rates, learning_sr,
    evaluation_sr, overall_sr) and only feed ``t6_oracle_pass_rate`` /
    ``t6_oracle_uplift``. This keeps the headline numbers comparable with
    non-dual baselines.
    """
    records = list(records)
    primary_records = [
        r for r in records if getattr(r, "replay_mode", "primary") == "primary"
    ]
    shadow_records = [
        r for r in records if getattr(r, "replay_mode", "primary") == "shadow_oracle"
    ]

    by_role: dict[str, list[ReplayRecord]] = {}
    for r in primary_records:
        by_role.setdefault(r.task_role, []).append(r)

    def _pass_rate(role: str) -> float:
        rs = by_role.get(role, [])
        if not rs:
            return 0.0
        return sum(1 for r in rs if r.outcome.verifier_passed) / len(rs)

    def _trap_resistance() -> float:
        """T5 trap_resistance: require BOTH verifier_passed AND
        process_passed (when known). Falls back to verifier_passed alone
        when process_report.json wasn't produced (None)."""
        rs = by_role.get(TaskRole.ADVERSARIAL.value, [])
        if not rs:
            return 0.0
        n_correct = 0
        for r in rs:
            if not r.outcome.verifier_passed:
                continue
            if r.outcome.process_passed is False:
                continue  # explicitly failed process check
            n_correct += 1
        return n_correct / len(rs)

    def _aggregate(roles: Iterable[str]) -> float:
        total: list[bool] = []
        for role in roles:
            total.extend(r.outcome.verifier_passed for r in by_role.get(role, []))
        if not total:
            return 0.0
        return sum(1 for v in total if v) / len(total)

    primary_t6 = _pass_rate(TaskRole.COMPOSITION.value)

    # Dual-T6 shadow trials: paired retrieval-only delta on T6.
    t6_oracle_pass_rate: Optional[float] = None
    t6_oracle_uplift: Optional[float] = None
    if shadow_records:
        n_pass = sum(1 for r in shadow_records if r.outcome.verifier_passed)
        t6_oracle_pass_rate = n_pass / len(shadow_records)
        t6_oracle_uplift = t6_oracle_pass_rate - primary_t6

    return TaskSuccessReport(
        t1_pass_rate=_pass_rate(TaskRole.CANONICAL.value),
        t2_pass_rate=_pass_rate(TaskRole.ENRICHED.value),
        t3_pass_rate=_pass_rate(TaskRole.VARIANT.value),
        t4_transfer=_pass_rate(TaskRole.CONTEXT_SHIFT.value),
        t5_pass_rate=_pass_rate(TaskRole.ADVERSARIAL.value),
        t5_trap_resistance=_trap_resistance(),
        t6_composition_rate=primary_t6,
        learning_sr=_aggregate(_LEARNING_ROLES),
        learning_sr_t2_t3=_aggregate({TaskRole.ENRICHED.value, TaskRole.VARIANT.value}),
        evaluation_sr=_aggregate(_EVAL_ROLES),
        overall_sr=_aggregate(_LEARNING_ROLES | _EVAL_ROLES),
        n_per_role={role: len(rs) for role, rs in by_role.items()},
        t6_oracle_pass_rate=t6_oracle_pass_rate,
        t6_oracle_uplift=t6_oracle_uplift,
        n_t6_oracle_shadow_trials=len(shadow_records),
    )


__all__ = ["TaskSuccessReport", "compute_task_success"]
