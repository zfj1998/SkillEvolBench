"""Retrieval metrics (Part 10 §12.3).

Aggregates over ``retrieval_events.jsonl`` (already pre-computed P@k / R@k /
required_skill_hit at write time, so this is a streaming aggregation).

Three classes of records:

* T1-T5 retrievals (no required_skills) -- contribute to wrong-skill-rate
  + retrieval-coverage.
* T6 retrievals (with required_skills) -- contribute to required-skill-hit-rate +
  P@k / R@k.
* All retrievals -- retrieval-coverage (was anything retrieved at all?).
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import RetrievalEvent


@dataclass
class RetrievalReport:
    n_events: int = 0

    # T6 oracle-comparison metrics
    n_t6_with_required: int = 0
    required_skill_hit_rate: float = 0.0
    mean_precision_at_k: Optional[float] = None
    mean_recall_at_k: Optional[float] = None

    # General retrieval health
    retrieval_coverage: float = 0.0  # fraction of events with at least one skill returned
    mean_top_score: Optional[float] = None

    # Wrong / cross-env retrieval (heuristic)
    wrong_skill_rate: float = 0.0
    cross_env_misretrieval_rate: float = 0.0

    # Per-task-id (for analysis)
    per_task_required_hit: dict[str, bool] = field(default_factory=dict)


def compute_retrieval_metrics(
    events: Iterable[RetrievalEvent],
) -> RetrievalReport:
    """Aggregate retrieval events into a report.

    ``wrong_skill_rate`` is computed for events with a non-empty
    ``required_skill_ids``: it's the fraction of *retrieved* skills that
    are NOT in the required list. (Lower is better.)

    ``cross_env_misretrieval_rate`` is the fraction of T6 retrievals that
    surfaced any skill from an environment OTHER than the task's own. The
    task_id encodes the env in its prefix (``E<n>-LS<m>-T<r>``).
    """
    evs = list(events)
    rep = RetrievalReport(n_events=len(evs))
    if not evs:
        return rep

    # T6 oracle-comparison metrics
    t6 = [e for e in evs if e.required_skill_ids]
    rep.n_t6_with_required = len(t6)
    if t6:
        hits = [e.required_skill_hit for e in t6 if e.required_skill_hit is not None]
        if hits:
            rep.required_skill_hit_rate = sum(1 for h in hits if h) / len(hits)
        ps = [e.precision_at_k for e in t6 if e.precision_at_k is not None]
        rs = [e.recall_at_k for e in t6 if e.recall_at_k is not None]
        if ps:
            rep.mean_precision_at_k = sum(ps) / len(ps)
        if rs:
            rep.mean_recall_at_k = sum(rs) / len(rs)
        rep.per_task_required_hit = {
            e.task_id: bool(e.required_skill_hit) for e in t6
            if e.required_skill_hit is not None
        }

    # General retrieval health
    n_with_skills = sum(1 for e in evs if e.retrieved_skill_ids)
    rep.retrieval_coverage = n_with_skills / rep.n_events

    top_scores = [e.scores[0] for e in evs if e.scores]
    if top_scores:
        rep.mean_top_score = sum(top_scores) / len(top_scores)

    # Wrong skill rate: fraction of retrieved skills NOT in required (T6 only).
    if t6:
        total_retrieved = 0
        total_wrong = 0
        for e in t6:
            req = set(e.required_skill_ids)
            for sid in e.retrieved_skill_ids:
                total_retrieved += 1
                if sid not in req:
                    total_wrong += 1
        if total_retrieved > 0:
            rep.wrong_skill_rate = total_wrong / total_retrieved

    # Cross-env misretrieval (T6 only)
    if t6:
        misretrievals = 0
        for e in t6:
            task_env = e.task_id.split("-", 1)[0]  # E1-LS1-T6 -> E1
            for sid in e.retrieved_skill_ids:
                # latent_skill_id = "E<x>-LS<y>.slug"
                env = sid.split("-", 1)[0]
                if env != task_env:
                    misretrievals += 1
                    break
        rep.cross_env_misretrieval_rate = misretrievals / len(t6)

    return rep


__all__ = ["RetrievalReport", "compute_retrieval_metrics"]
