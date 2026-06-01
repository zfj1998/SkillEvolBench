"""Skill revision strategies.

Public strategies:

* :class:`ChainEvolution` -- single-candidate revision.
* ``chain_tier3``         -- ChainEvolution with a Tier-3 artifact constraint.
* :class:`NullStrategy`   -- no-op for baselines that do not revise.
"""

from typing import Any, Optional

from skillevolbench.strategies.base import (
    ApplyPatch,
    EvolutionContext,
    EvolutionDecision,
    EvolutionStrategy,
    NoOp,
)
from skillevolbench.strategies.chain import ChainEvolution
from skillevolbench.strategies.null import NullStrategy


def build_strategy(
    *,
    name: str,
    evolver: Optional[Any],
    retriever: Optional[Any],
    library: Any,
    replay_store: Optional[Any],
    event_store: Any,
    config: Any,
) -> EvolutionStrategy:
    """Build the runtime strategy selected by ``RunConfig.strategy``."""
    if name == "none":
        return NullStrategy()
    if name in ("chain", "chain_tier3"):
        return ChainEvolution(
            evolver=evolver,
            retriever=retriever,
            library=library,
            replay_store=replay_store,
            event_store=event_store,
            config=config,
        )
    raise ValueError(f"Unknown strategy name: {name!r}")


__all__ = [
    "ApplyPatch",
    "NoOp",
    "EvolutionDecision",
    "EvolutionContext",
    "EvolutionStrategy",
    "ChainEvolution",
    "NullStrategy",
    "build_strategy",
]
