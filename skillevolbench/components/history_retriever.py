"""HistoryRetriever -- raw history-context control baseline.

Used by ``History-Context-Control`` (currently dropped from the canonical
ladder, kept here in case it returns as an extra ablation).

At trial start, concatenate compacted trajectories of past tasks into a
single string, capped at ``max_tokens`` characters/4 (chars-per-token
approximation).

Same-family + learning-block scope: matches TrajectoryRetriever for
symmetry. Cross-family / eval-block records would conflate "memory" with
"agent-being-tested" content, breaking the differential vs path-A/B.

Order: most recent first. Within a single past task we use its
``CompactedTrajectory.text``. The buffer is truncated *between* tasks --
never mid-task -- so the LLM sees coherent units.
"""

from __future__ import annotations

import logging
from typing import Any

from skillevolbench.schemas import ReplayRecord


_LOG = logging.getLogger(__name__)


# Mirrors trajectory_retriever._LEARNING_ROLES; duplicated to avoid a
# cross-component import cycle.
_LEARNING_ROLES: frozenset[str] = frozenset({"canonical", "enriched", "variant"})


class HistoryRetriever:
    """Build a prompt-ready history string from a :class:`ReplayStore`.

    Restricted to the current task's family + learning-block roles; same
    rationale as TrajectoryRetriever's docstring.
    """

    def __init__(self, replay_store: Any) -> None:
        self.replay_store = replay_store

    def build_context(self, task: Any, max_tokens: int) -> str:
        if max_tokens <= 0:
            return ""

        budget_chars = max_tokens * 4
        # Most recent first. Same family + T1-T3 only; exclude self.
        family_id = getattr(task, "family_id", None)
        if not family_id:
            return ""
        family_records = self.replay_store.tasks_by_family(family_id)
        records = sorted(
            (
                r for r in family_records
                if r.task_id != task.task_id
                and getattr(r, "task_role", "") in _LEARNING_ROLES
            ),
            key=lambda r: r.timestamp,
            reverse=True,
        )

        parts: list[str] = []
        used = 0
        for r in records:
            chunk = self._render_record(r)
            if used + len(chunk) > budget_chars:
                # Stop on a clean task boundary; do not truncate mid-task.
                break
            parts.append(chunk)
            used += len(chunk)
        return "\n\n".join(parts)

    @staticmethod
    def _render_record(record: ReplayRecord) -> str:
        verdict = "PASSED" if record.outcome.verifier_passed else "FAILED"
        body = record.trajectory_compact.get("text") or "(no compacted text)"
        if isinstance(body, str) and len(body) > 4000:
            body = body[:4000] + "..."
        return (
            f"### Past task {record.task_id} ({verdict}, "
            f"reward={record.outcome.reward:.2f})\n\n{body}"
        )


__all__ = ["HistoryRetriever"]
