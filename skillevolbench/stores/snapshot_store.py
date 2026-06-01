"""SnapshotStore: named git tags over the LibraryStore.

One responsibility: tag the current ``HEAD`` of the library git repo with a
human-readable name. The runner and hooks use tags for per-environment
checkpoints and the final run snapshot.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING


_LOG = logging.getLogger(__name__)


if TYPE_CHECKING:
    from skillevolbench.stores.library_store import LibraryStore


class SnapshotStore:
    """Wrap LibraryStore's git wrapper to expose a tag-only API."""

    def __init__(self, library: "LibraryStore"):
        self.library = library

    @property
    def _git(self):
        # Access the git wrapper attached to the library. We don't import it
        # here to avoid leaking subprocess details into the public surface.
        return self.library._git  # type: ignore[attr-defined]

    def tag(self, name: str, message: str | None = None) -> None:
        """Create an annotated tag on the library HEAD. No-op when the tag
        already exists -- a re-run resuming mid-stream should not crash."""
        if self._git.has_tag(name):
            _LOG.debug("SnapshotStore.tag: tag %r already exists -- skipping", name)
            return
        self._git.tag(name, message=message or f"SkillEvolBench snapshot: {name}")

    def has_tag(self, name: str) -> bool:
        return self._git.has_tag(name)


__all__ = ["SnapshotStore"]
