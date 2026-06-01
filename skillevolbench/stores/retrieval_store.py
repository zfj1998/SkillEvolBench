"""Retrieval-event jsonl with inline P@k / R@k (Part 5 §5.4).

One file per run: ``stores/retrieval/retrieval_events.jsonl``.

Per-trial entries record the retriever's top-k output plus, if the task is
T6 with ``required_skills``, the precision_at_k / recall_at_k computed
inline at write time. This lets the analysis pipeline compute
Required-Skill-Hit-Rate, Wrong-Skill-Retrieval-Rate, Retrieval-Coverage
without reloading the library.

The full ranking is truncated to top 50 to keep the jsonl bounded.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Optional

from skillevolbench.schemas import RetrievalEvent, RetrievalResult


_LOG = logging.getLogger(__name__)
_FULL_RANKING_LIMIT = 50


class RetrievalStore:
    """Write a jsonl event per retrieval call."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.log_path = self.root / "retrieval_events.jsonl"

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(
        self,
        task_id: str,
        retrieval: RetrievalResult,
        required_skills: list[str] | None = None,
    ) -> RetrievalEvent:
        retrieved_ids = retrieval.skill_ids
        required = list(required_skills or [])
        precision = self._precision_at_k(retrieved_ids, required)
        recall = self._recall_at_k(retrieved_ids, required)
        hit = self._required_hit(retrieved_ids, required)

        event = RetrievalEvent(
            ts=datetime.now(timezone.utc),
            task_id=task_id,
            retrieved_skill_ids=retrieved_ids,
            scores=list(retrieval.scores),
            full_ranking=list(retrieval.full_ranking[:_FULL_RANKING_LIMIT]),
            required_skill_ids=required,
            precision_at_k=precision,
            recall_at_k=recall,
            required_skill_hit=hit,
        )
        with self.log_path.open("a") as f:
            f.write(event.model_dump_json() + "\n")
        return event

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def all_events(self) -> list[RetrievalEvent]:
        if not self.log_path.exists():
            return []
        out: list[RetrievalEvent] = []
        for line in self._iter_lines():
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                _LOG.warning("retrieval_store: skipping malformed line")
                continue
            out.append(RetrievalEvent.model_validate(obj))
        return out

    def event_for(self, task_id: str) -> Optional[RetrievalEvent]:
        for ev in self.all_events():
            if ev.task_id == task_id:
                return ev
        return None

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _iter_lines(self) -> Iterable[str]:
        with self.log_path.open() as f:
            for line in f:
                line = line.rstrip("\n")
                if line:
                    yield line

    @staticmethod
    def _precision_at_k(retrieved: list[str], required: list[str]) -> Optional[float]:
        if not required:
            return None
        if not retrieved:
            return 0.0
        return len(set(retrieved) & set(required)) / len(retrieved)

    @staticmethod
    def _recall_at_k(retrieved: list[str], required: list[str]) -> Optional[float]:
        if not required:
            return None
        return len(set(retrieved) & set(required)) / len(required)

    @staticmethod
    def _required_hit(
        retrieved: list[str], required: list[str]
    ) -> Optional[bool]:
        if not required:
            return None
        return set(required).issubset(set(retrieved))


__all__ = ["RetrievalStore"]
