"""TrajectoryExtractor -- accurate per-CLI skill engagement.

Walks ATIF ``trajectory.json`` and reports which skills the agent actually
opened. The legacy implementation regex'd over the full JSON-stringified
trajectory text -- which silently matched ``/skills/<slug>/`` references in
the **user message** (i.e. our own ``# Available Skills`` prompt injection)
and in **observation** blobs (e.g. ``ls /skills/`` output), inflating
``skills_actually_used`` with skills the agent never touched. After we
removed the prompt section the user-message channel went quiet, but the
observation channel and any other path embedded in non-tool-call text was
still being counted. This module fixes both by restricting matches to
**agent tool_call arguments only**, with per-CLI handling:

================  ============================  =====================================
CLI               function_name                 argument shape
================  ============================  =====================================
Claude Code       ``Read`` / ``Edit`` / etc.    ``{"file_path": "/skills/<slug>/..."}``
Claude Code       ``Skill``                     ``{"skill": "<slug>"}``  (slug, not path)
OpenAI Codex      ``exec_command``              ``{"cmd": "sed -n '1,N' /root/.agents/skills/<slug>/..."}``
Gemini CLI        ``run_shell_command``         ``{"command": "cat /skills/<slug>/...", "description": "..."}``
Kimi / others     ``shell`` / ``execute_command``  ``{"command": "...", ...}``
================  ============================  =====================================

If the trajectory file isn't valid JSON or doesn't expose a ``steps`` list
(e.g. a flat Claude ``.txt`` stream), we fall back to a text-mode regex
scan -- the legacy behaviour, kept only for non-ATIF formats so the
metric is never silently empty.

Outputs feed:

* mechanism metrics that need "Effective Skill Count" (skills used in eval)
* RGPE replay-set selection (tasks that used a touched skill)
* Library-Health Stale Rate (skills never used)
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path
from typing import Any, Iterable, Optional


_LOG = logging.getLogger(__name__)


# Match the 5 mount targets we bind ``library/active/`` to inside trial
# containers (see harbor_ext/env.py). Captures the slug right after the
# mount root. Requires at least one slug character so a bare ``ls /skills/``
# does NOT match.
_SKILL_PATH_RE = re.compile(
    r"(?:/skills"
    r"|/root/\.claude/skills"
    r"|/root/\.gemini/skills"
    r"|/root/\.agents/skills"
    r"|/root/\.kimi/skills"
    r")/([A-Za-z0-9][A-Za-z0-9_\-\.]*)\b"
)

# Legacy alias for back-compat: ``compactor._referenced_skills`` imports it
# to populate ``CompactedTrajectory.skills_referenced``. The text-mode scan
# is the right semantics there (compactor surveys the WHOLE event payload
# for "what skills did this trajectory mention", not just tool calls), so
# the alias keeps the one-shot regex behaviour intact.
_SKILL_REF_RE = _SKILL_PATH_RE


# Tools whose first argument is a file path. Slugs are extracted from the
# path string. Includes Claude Code file tools and a couple of generic
# variants used by other CLIs.
_PATH_TOOLS: frozenset[str] = frozenset({
    "Read", "Edit", "Write", "MultiEdit", "Glob", "Grep",
    "NotebookRead", "NotebookEdit",
    "read_file", "write_file", "view_file",
})
_PATH_ARG_KEYS: tuple[str, ...] = ("file_path", "path", "files", "filename")

# Tools that execute a shell command. Slugs come from any path inside the
# command string. Covers Claude Code's ``Bash``, Codex's ``exec_command``,
# Gemini's ``run_shell_command``, plus generic variants.
_SHELL_TOOLS: frozenset[str] = frozenset({
    "Bash", "exec_command", "run_shell_command",
    "shell", "execute_command", "run_command", "Run",
})
_SHELL_ARG_KEYS: tuple[str, ...] = ("command", "cmd", "script", "shell_command")

# Direct skill-launching tools: the slug is given by NAME, not by path.
# Claude Code's ``Skill`` tool is the canonical example (``Sonnet`` uses
# it heavily). The arg is the slug exactly as it appears on disk.
_SKILL_TOOLS: frozenset[str] = frozenset({
    "Skill",
})
_SKILL_ARG_KEYS: tuple[str, ...] = ("skill", "skill_name", "name", "slug")


class TrajectoryExtractor:
    """Extract the set of skill_ids the agent actually opened.

    The container path uses the on-disk slug (per Anthropic SKILL.md spec
    folder=name); we translate captured slugs back to the formal
    ``latent_skill_id`` via the library's manifest. Pass ``library`` to
    enable translation; without it, raw slugs are returned (informational
    only).
    """

    def extract_skills_used(
        self,
        trajectory_path: Optional[Path],
        *,
        library: Any = None,
    ) -> list[str]:
        """Return a sorted, deduped list of skill ids the agent touched.

        Returns ``[]`` when the path is missing or unreadable -- this is
        OK because the metric pipeline distinguishes "no skill used" (the
        agent ignored retrieval) from "trajectory missing" via the
        trajectory path's existence.
        """
        if trajectory_path is None or not Path(trajectory_path).exists():
            return []
        path = Path(trajectory_path)
        slugs = self._collect_slugs(path)
        if not slugs:
            return []
        if library is None:
            return sorted(slugs)
        # Translate slug -> formal latent_skill_id via manifest reverse-lookup.
        # Slugs that don't map to a known skill are dropped -- they may be
        # built-in CLI skills (e.g. Claude Code's ``debug``, ``simplify``)
        # that share the namespace via the bind-mount but aren't part of our
        # benchmark library.
        from skillevolbench.stores.library_store import skill_id_to_slug
        try:
            manifest = library._load_manifest()  # noqa: SLF001
        except AttributeError:
            return sorted(slugs)
        slug_to_sid: dict[str, str] = {}
        for sid in manifest.skills:
            slug_to_sid.setdefault(skill_id_to_slug(sid), sid)
        return sorted({slug_to_sid[s] for s in slugs if s in slug_to_sid})

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @classmethod
    def _collect_slugs(cls, path: Path) -> set[str]:
        """Top-level dispatch: try ATIF JSON walk, fall back to text scan."""
        try:
            text = path.read_text(errors="replace")
        except OSError:
            return set()

        # ATIF path: parse + walk steps + extract from agent tool_calls only.
        if path.suffix == ".json":
            try:
                obj = json.loads(text)
            except json.JSONDecodeError:
                obj = None
            if isinstance(obj, dict) and isinstance(obj.get("steps"), list):
                return cls._slugs_from_atif(obj)

        # Fallback: text-mode regex over the raw file. Used for
        # non-ATIF agent logs (e.g. flat Claude ``.txt`` streams from
        # older harness versions). This may over-count -- it cannot
        # distinguish prompt/observation references from real tool
        # calls -- but is preferable to dropping the signal entirely.
        return cls._slugs_from_text(text)

    @classmethod
    def _slugs_from_atif(cls, atif: dict) -> set[str]:
        """Walk ATIF steps, extract slugs from agent tool_call args only."""
        slugs: set[str] = set()
        for step in atif.get("steps") or []:
            if not isinstance(step, dict):
                continue
            if step.get("source") != "agent":
                continue
            tool_calls = step.get("tool_calls") or []
            if not isinstance(tool_calls, list):
                continue
            for tc in tool_calls:
                slugs |= cls._slugs_from_tool_call(tc)
        return slugs

    @classmethod
    def _slugs_from_tool_call(cls, tc: Any) -> set[str]:
        """Per-CLI dispatch: pick the right arg field based on tool name."""
        if not isinstance(tc, dict):
            return set()

        name = (
            tc.get("function_name")
            or tc.get("name")
            or tc.get("tool")
            or ""
        )
        args = (
            tc.get("arguments")
            or tc.get("args")
            or tc.get("input")
            or {}
        )
        # Some CLIs serialize arguments as a JSON string. Normalize.
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except (json.JSONDecodeError, ValueError):
                # Treat as a single opaque blob and scan it as text.
                return cls._slugs_from_text(args)
        if not isinstance(args, dict):
            return set()

        # Case 1: direct skill invocation -- slug given by name.
        # We don't validate against the library here; the caller
        # filters via manifest translation. The slug must look like a
        # plausible identifier (not e.g. an empty string or path).
        if name in _SKILL_TOOLS:
            for k in _SKILL_ARG_KEYS:
                v = args.get(k)
                if isinstance(v, str):
                    cleaned = v.strip().strip("/").rstrip(".")
                    if cleaned and "/" not in cleaned and " " not in cleaned:
                        return {cleaned}
            return set()

        # Case 2: file-path tools -- one or more path-shaped args.
        if name in _PATH_TOOLS:
            return cls._extract_from_arg_keys(args, _PATH_ARG_KEYS)

        # Case 3: shell tools -- slugs hide inside the command string.
        if name in _SHELL_TOOLS:
            return cls._extract_from_arg_keys(args, _SHELL_ARG_KEYS)

        # Case 4: unknown tool -- defensively scan every string value
        # in args. Catches CLI-specific tools we haven't enumerated
        # without re-introducing the whole-trajectory false-match
        # problem (we still don't look at observations / messages).
        slugs: set[str] = set()
        for v in args.values():
            if isinstance(v, str):
                slugs |= cls._slugs_from_text(v)
        return slugs

    @classmethod
    def _extract_from_arg_keys(
        cls, args: dict, keys: Iterable[str],
    ) -> set[str]:
        slugs: set[str] = set()
        for k in keys:
            v = args.get(k)
            if isinstance(v, str):
                slugs |= cls._slugs_from_text(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, str):
                        slugs |= cls._slugs_from_text(item)
        return slugs

    @staticmethod
    def _slugs_from_text(text: str) -> set[str]:
        """Match any of the 5 skill mount roots in a string; capture slug."""
        out: set[str] = set()
        for m in _SKILL_PATH_RE.finditer(text):
            sid = m.group(1).rstrip("./")
            if sid:
                out.add(sid)
        return out


__all__ = ["TrajectoryExtractor"]
