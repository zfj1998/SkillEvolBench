"""Type protocols for the Harbor integration layer (Part 4).

The hook in ``hooks.py`` is dispatched against a *runtime object* that
aggregates Part 5-8 services (LibraryStore, EventStore, Strategy, ...). To
avoid circular imports and to keep the hook importable on machines without
the Harbor SDK installed, we describe the runtime via ``typing.Protocol``
rather than importing the concrete ``BaselineRuntime`` class (which is Part
8's ownership).

The protocol is deliberately *loose* (most fields are typed as ``Any``)
because the hook only forwards calls -- the real type-checking happens at
each individual store / component / strategy method.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

if TYPE_CHECKING:
    from skillevolbench.schemas import BaselineConfig


@runtime_checkable
class RuntimeProtocol(Protocol):
    """The set of attributes ``SkillEvolBenchHooks`` reads off the runtime.

    Part 8's ``BaselineRuntime`` will satisfy this protocol. Tests can supply
    a ``SimpleNamespace`` mock with the same attributes.
    """

    # ===== Part 3 config =====
    baseline: "BaselineConfig"

    # ===== Part 5 stores =====
    library: Any                # LibraryStore | NullLibrary
    event_store: Any            # EventStore
    replay_store: Any           # ReplayStore
    retrieval_store: Any        # RetrievalStore
    snapshot_store: Any         # SnapshotStore | None

    # ===== Part 6 components =====
    retriever: Any              # SkillRetriever | None
    trajectory_retriever: Any   # TrajectoryRetriever | None
    history_retriever: Any      # HistoryRetriever | None
    evolver: Any                # SkillAuthor | None
    freeze_ctrl: Any            # LibraryFreezeController
    compactor: Any              # TrajectoryCompactor
    verifier_adapter: Any       # VerifierAdapter
    trajectory_extractor: Any   # TrajectoryExtractor

    # ===== Part 7 strategy =====
    strategy: Any               # EvolutionStrategy

    # ===== Run identity =====
    run_root: Path


@runtime_checkable
class TaskRegistryProtocol(Protocol):
    """Subset of ``TaskRegistry`` (Part 1) accessed by the hook."""

    def task(self, task_id: str) -> Any: ...
    def task_by_slug(self, slug: str) -> Any: ...
    def family(self, family_id: str) -> Any: ...


@runtime_checkable
class RuntimeBuilderProtocol(Protocol):
    """``RuntimeBuilder`` (Part 6) as seen by the hook."""

    def build(
        self,
        *,
        task: Any,
        run_root: Path,
        baseline: "BaselineConfig",
        retrieved_skills: list,
        retrieved_trajectories: list,
        history_context: str | None,
        library_frozen: bool,
        runtime_basename: str | None = None,
    ) -> Path: ...


@runtime_checkable
class PromptBuilderProtocol(Protocol):
    """``PromptBuilder`` (Part 6). Currently unused directly by the hook
    (RuntimeBuilder dispatches), kept for symmetry."""

    def build(
        self,
        *,
        original_instruction: str,
        baseline: "BaselineConfig",
        task: Any,
        retrieved_skills: list,
        retrieved_trajectories: list,
        history_context: str | None,
        library_frozen: bool,
    ) -> str: ...


__all__ = [
    "RuntimeProtocol",
    "TaskRegistryProtocol",
    "RuntimeBuilderProtocol",
    "PromptBuilderProtocol",
]
