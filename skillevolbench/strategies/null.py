"""``NullStrategy`` -- a no-op strategy used for baselines that do not revise.

When :class:`BaselineConfig.default_strategy == "none"` (No-Skill,
Curated-Static, Curated-with-Feedback-Memory, Self-Gen-Zero-Shot,
Raw-Trajectory-RAG, History-Context-Control), Part 8 wires this. The hook
still calls ``decide(...)`` but always gets ``NoOp``.

This is symmetric with the other three strategies (Chain / Tree / RGPE)
so the runtime never has to special-case "no strategy".
"""

from __future__ import annotations

from skillevolbench.strategies.base import (
    EvolutionContext,
    EvolutionStrategy,
    NoOp,
)


class NullStrategy(EvolutionStrategy):
    name: str = "none"

    def __init__(self, **kwargs) -> None:  # signature compatible with peers
        # Allow construction with no dependencies at all.
        kwargs.setdefault("evolver", None)
        kwargs.setdefault("retriever", None)
        kwargs.setdefault("library", None)
        kwargs.setdefault("replay_store", None)
        kwargs.setdefault("event_store", None)
        kwargs.setdefault("config", None)
        super().__init__(**kwargs)

    def _decide_impl(self, ctx: EvolutionContext) -> NoOp:
        return NoOp(reason="null_strategy")


__all__ = ["NullStrategy"]
