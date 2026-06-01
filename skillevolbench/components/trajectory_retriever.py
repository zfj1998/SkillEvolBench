"""TrajectoryRetriever -- raw-trajectory RAG control baseline.

Used by ``Raw-Trajectory-RAG``. At trial start, fetch the past **learning-
block** trajectories of the same family (chronological T1 -> T2 -> T3
chain) and surface their compacted text in the prompt.

Design rules:

1. **Same family only.** Cross-family fallback was removed -- raw traces
   from unrelated families are noise, and dropping them keeps the
   abstraction-vs-memory comparison against path-A/B clean.
2. **Learning-block roles only.** Eval-block records (context-shift,
   adversarial, composition) are persisted in :class:`ReplayStore` for
   metrics + retention replay, but they are **not** part of the "memory"
   that the lifelong learner accumulated:

   * Evolution (SkillAuthor) does not run during T4-T6 (the protocol
     freezes the library). So path-A/B libraries only reflect T1-T3
     contributions.
   * For symmetry, raw_trajectory_rag's "memory" must also be T1-T3 only.
   * Otherwise running T5 might surface T4's trace as if it were learned
     content, which conflates "agent being tested" with "agent learning".
3. ``tasks_by_family`` returns records in ``ORDER BY timestamp`` ascending,
   so the natural ordering is T1 -> T2 -> T3.

Implications:

* T1 of any family runs with an empty ``# Retrieved Past Trajectories``
  section -- the family has no prior experience yet.
* T2 sees T1; T3 sees T1+T2.
* T4-T6 (eval block) all see exactly T1+T2+T3 -- the same content path-A/B
  would have used to seed their library.
"""

from __future__ import annotations

import logging
from typing import Any

from skillevolbench.schemas import ReplayRecord


_LOG = logging.getLogger(__name__)


# Learning-block role names. Mirrors ``_LEARNING_ROLES`` in scheduler.py and
# strategies/base.py; kept locally to avoid an import cycle.
_LEARNING_ROLES: frozenset[str] = frozenset({"canonical", "enriched", "variant"})


class TrajectoryRetriever:
    """Return the same-family, learning-block chronological chain."""

    def __init__(self, replay_store: Any) -> None:
        self.replay_store = replay_store

    def retrieve(self, task: Any, k: int) -> list[ReplayRecord]:
        if k <= 0:
            return []
        chain = [
            r
            for r in self.replay_store.tasks_by_family(task.family_id)
            if r.task_id != task.task_id
            and getattr(r, "task_role", "") in _LEARNING_ROLES
        ]
        return chain[:k]


__all__ = ["TrajectoryRetriever"]
