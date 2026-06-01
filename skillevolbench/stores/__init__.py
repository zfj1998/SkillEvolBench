"""Persistence layer for benchmark runs.

Stores backing the lifelong protocol:

* ``LibraryStore``   -- git-versioned global or per-environment skill library
* ``NullLibrary``    -- drop-in library for baselines without skill memory
* ``ReplayStore``    -- sqlite + per-task json replay records
* ``EventStore``     -- 3-channel append-only jsonl audit log
* ``RetrievalStore`` -- per-trial retrieval jsonl with inline P@k / R@k
* ``SnapshotStore``  -- git-tag wrapper over LibraryStore for checkpointing
"""

from skillevolbench.stores.library_store import LibraryStore, NullLibrary
from skillevolbench.stores.replay_store import ReplayStore
from skillevolbench.stores.event_store import EventStore
from skillevolbench.stores.retrieval_store import RetrievalStore
from skillevolbench.stores.snapshot_store import SnapshotStore


__all__ = [
    "LibraryStore",
    "NullLibrary",
    "ReplayStore",
    "EventStore",
    "RetrievalStore",
    "SnapshotStore",
]
