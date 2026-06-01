"""Retrieval schemas (Part 5/6).

``RetrievalResult`` is what ``Retriever.retrieve(query, library, k)`` returns.
``RetrievalEvent`` is what ``RetrievalStore`` writes to its jsonl log.
``RetrievalStore`` computes precision_at_k / recall_at_k inline at write time
so the replay analysis pipeline can stream the jsonl without reloading the
library state.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class RetrievedSkill(BaseModel):
    """One skill returned by the retriever; references the manifest entry by id."""

    skill_id: str
    score: float = 0.0
    name: Optional[str] = None
    description: Optional[str] = None


class RetrievalResult(BaseModel):
    """The k retrieved skills + the full ranking (truncated to top 50 in
    ``RetrievalStore.record`` to bound the jsonl size)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    skills: list[RetrievedSkill] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    full_ranking: list[tuple[str, float]] = Field(default_factory=list)
    query_text: str = ""

    @property
    def skill_ids(self) -> list[str]:
        return [s.skill_id for s in self.skills]


class RetrievalEvent(BaseModel):
    """One row of ``retrieval_events.jsonl``."""

    ts: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    task_id: str
    retrieved_skill_ids: list[str] = Field(default_factory=list)
    scores: list[float] = Field(default_factory=list)
    full_ranking: list[tuple[str, float]] = Field(default_factory=list)

    # Ground truth from task-spec.yaml (T6 only); empty for T1-T5.
    required_skill_ids: list[str] = Field(default_factory=list)

    # Pre-computed at write time (cheaper than recomputing during analysis).
    precision_at_k: Optional[float] = None
    recall_at_k: Optional[float] = None
    required_skill_hit: Optional[bool] = None


__all__ = [
    "RetrievedSkill",
    "RetrievalResult",
    "RetrievalEvent",
]
