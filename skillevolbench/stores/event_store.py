"""Audit event store -- append-only jsonl.

Three jsonl channels:

* ``lifecycle.jsonl``  -- trial lifecycle, env transitions, freeze/unfreeze
* ``patches.jsonl``    -- patch_proposed / patch_applied / patch_rejected
                          / rollback / noop / candidate_failed
* ``system.jsonl``     -- asset / resume / system events

Routing: ``EventStore.record(event_type, payload)`` walks
``EVENT_PREFIX_TO_CHANNEL`` (from ``schemas/event.py``) to decide which file.
Events with no matching prefix go to ``lifecycle.jsonl`` (the default
channel for trial lifecycle).

Append-only: never rewrite, never reorder. Any analysis pipeline can
``tail`` the files. The 'patch_proposed / patch_applied / patch_rejected'
sequence is sufficient to reconstruct the full strategy decision history.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable, Optional

from skillevolbench.schemas.event import (
    EVENT_PREFIX_TO_CHANNEL,
    DEFAULT_CHANNEL,
)
from skillevolbench.schemas.skill import ApplyResult, SkillPatch


_LOG = logging.getLogger(__name__)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class EventStore:
    """Append-only jsonl writer with per-event routing."""

    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.lifecycle_path = self.root / "lifecycle.jsonl"
        self.patches_path = self.root / "patches.jsonl"
        self.system_path = self.root / "system.jsonl"

    # ------------------------------------------------------------------
    # Generic record API used by everything (hooks, lifecycle, etc.)
    # ------------------------------------------------------------------

    def record(self, event_type: str, payload: dict[str, Any]) -> None:
        line = {"ts": _now_iso(), "event_type": event_type, **payload}
        self._append(self._route(event_type), line)

    # ------------------------------------------------------------------
    # Patch-specific helpers
    # ------------------------------------------------------------------

    def record_patch_proposed(
        self, patch: SkillPatch, strategy_name: str
    ) -> None:
        self._append_patch_event(
            event_type="patch_proposed",
            patch=patch,
            strategy=strategy_name,
        )

    def record_patch_applied(
        self,
        patch: SkillPatch,
        apply_result: ApplyResult,
        strategy_name: str,
    ) -> None:
        self._append_patch_event(
            event_type="patch_applied",
            patch=patch,
            strategy=strategy_name,
            extra={
                "apply_result": apply_result.model_dump(mode="json"),
            },
        )

    def record_patch_rejected(
        self,
        patch: SkillPatch,
        reason: str,
        gate_results: Optional[dict[str, Any]] = None,
        strategy_name: str = "",
    ) -> None:
        self._append_patch_event(
            event_type="patch_rejected",
            patch=patch,
            strategy=strategy_name,
            extra={"reason": reason, "gate_results": gate_results or {}},
        )

    # ------------------------------------------------------------------
    # Read API (used by metric reporters)
    # ------------------------------------------------------------------

    def events_of_type(self, event_type: str) -> list[dict[str, Any]]:
        path = self._route(event_type)
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        for line in self._iter_lines(path):
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                _LOG.warning("event_store: skipping malformed line in %s", path)
                continue
            if obj.get("event_type") == event_type:
                out.append(obj)
        return out

    def all_events(self, channel: str | None = None) -> list[dict[str, Any]]:
        paths: list[Path]
        if channel == "lifecycle":
            paths = [self.lifecycle_path]
        elif channel == "patches":
            paths = [self.patches_path]
        elif channel == "system":
            paths = [self.system_path]
        elif channel is None:
            paths = [self.lifecycle_path, self.patches_path, self.system_path]
        else:
            raise ValueError(f"unknown channel: {channel!r}")
        out: list[dict[str, Any]] = []
        for path in paths:
            if not path.exists():
                continue
            for line in self._iter_lines(path):
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
        return out

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _route(self, event_type: str) -> Path:
        # Find the longest matching prefix, then map to channel.
        match = None
        for prefix in EVENT_PREFIX_TO_CHANNEL:
            if event_type.startswith(prefix):
                if match is None or len(prefix) > len(match):
                    match = prefix
        channel = EVENT_PREFIX_TO_CHANNEL.get(match, DEFAULT_CHANNEL)  # type: ignore[arg-type]
        return self._channel_path(channel)

    def _channel_path(self, channel: str) -> Path:
        return {
            "lifecycle": self.lifecycle_path,
            "patches": self.patches_path,
            "system": self.system_path,
        }[channel]

    @staticmethod
    def _append(path: Path, payload: dict[str, Any]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a") as f:
            f.write(json.dumps(payload, default=str) + "\n")

    @staticmethod
    def _iter_lines(path: Path) -> Iterable[str]:
        with path.open() as f:
            for line in f:
                line = line.rstrip("\n")
                if line:
                    yield line

    def _append_patch_event(
        self,
        *,
        event_type: str,
        patch: SkillPatch,
        strategy: str,
        extra: Optional[dict[str, Any]] = None,
    ) -> None:
        line: dict[str, Any] = {
            "ts": _now_iso(),
            "event_type": event_type,
            "patch_id": patch.patch_id,
            "strategy": strategy,
            "summary": patch.summary,
            "target_skill_ids": list(patch.target_skill_ids),
            "operation_type": patch.operation_type,
            "triggered_by_task": patch.triggered_by_task,
            "upsert_paths": list(patch.upsert_files.keys()),
            "delete_paths": list(patch.delete_paths),
        }
        if extra:
            line.update(extra)
        self._append(self.patches_path, line)


__all__ = ["EventStore"]
