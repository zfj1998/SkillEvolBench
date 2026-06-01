"""``GlobalLibraryEnvironment`` (Part 4 §4.1).

Subclasses Harbor's ``DockerEnvironment`` to add per-trial container mounts
that implement skill injection:

* **Per-agent native skill folders** -- the same ``library/active/`` host
  directory is bind-mounted to each of the four agent CLIs' canonical
  user-level skill folder so they can auto-discover skills via the
  agentskills.io progressive-disclosure mechanism (description in context
  Tier 1 -> body loaded on activation Tier 2 -> bundled files on demand
  Tier 3):

    ``/root/.claude/skills``   -- Claude Code (anthropic)
    ``/root/.gemini/skills``   -- Gemini CLI (google)
    ``/root/.agents/skills``   -- OpenAI Codex (and Gemini's universal alias)
    ``/root/.kimi/skills``     -- Kimi CLI (moonshot)

  Readonly when ``library/.frozen`` exists (eval-block invariant).

* ``/skills/`` -- legacy mount, kept because some agents (notably Claude
  Code Read calls and Gemini ``cat`` invocations) reach for this path
  out of habit. ``# Available Skills`` prompt injection has been removed
  (see PromptBuilder docstring), but the mount is harmless to retain and
  removing it would silently break those agents' default access pattern.
  Same data as the per-agent native folders, same readonly flag.

* ``/context/injection.json`` -- per-trial audit snapshot of what was
  retrieved + injected for this task. Read-only.

This module **hard-imports Harbor**; if ``harbor`` is not installed,
``import skillevolbench.harbor_ext.env`` will fail at module load. By
contrast, ``skillevolbench.harbor_ext.hooks`` is import-safe without
Harbor (uses ``TYPE_CHECKING``) so unit tests of the dispatch logic
don't require the Harbor SDK.

Wiring (Part 4 §4.3 ``build_job_config``)::

    JobConfig(
        environment=EnvironmentConfig(
            type=EnvironmentType.DOCKER,
            import_path="skillevolbench.harbor_ext.env:GlobalLibraryEnvironment",
            kwargs={
                "library_active_path": str(run_root / "library" / "active"),
                "library_readonly_marker": str(run_root / "library" / ".frozen"),
                "run_root": str(run_root),
            },
        ),
        ...
    )

Harbor instantiates this class once per trial. The ``trial_paths.trial_dir``
basename has the form ``<task_id>__<random>``, which is how we recover
``task_id`` to compute the per-trial ``injection-context.json`` path.

Migration note (Harbor 0.5 -> 0.6+)
-----------------------------------

Harbor 0.5 had a ``get_extra_mounts(trial_config)`` extension hook that
subclasses overrode to inject mounts at trial-start time. Harbor 0.6+
removed this hook entirely; mounts are now declared via the
``mounts_json: list[ServiceVolumeConfig]`` constructor parameter. We
compute our two mounts in ``__init__`` and pass them through to
``DockerEnvironment.__init__`` merged with whatever ``mounts_json`` the
caller provided.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

# These imports MUST succeed -- this module is only loaded when Harbor is
# available (e.g. via JobConfig.environment.import_path). When the SDK is
# missing, raising ImportError at module load is the correct behavior.
#
# Note the deep path: harbor.environments.docker is a *package* (directory
# with __init__.py exporting compose-yaml path constants), and the
# DockerEnvironment class itself lives in the inner ``docker.py`` module.
from harbor.environments.docker.docker import DockerEnvironment


_LOG = logging.getLogger(__name__)


class GlobalLibraryEnvironment(DockerEnvironment):
    """Harbor ``DockerEnvironment`` with the SkillEvolBench skill mounts.

    Constructor parameters (passed via ``EnvironmentConfig.kwargs``):

    Parameters
    ----------
    library_active_path
        Host path of the live ``library/active/`` directory.
    library_readonly_marker
        Host path of the ``.frozen`` marker file. Existence flips the
        ``/skills/`` mount to readonly.
    run_root
        Host path of the run's workspace root (``workspace/runs/<run_id>``).
        Used to compute the per-trial ``injection-context.json`` path.

    All remaining keyword arguments are forwarded to
    ``DockerEnvironment.__init__``. Harbor 0.6+ requires the standard
    parameters ``environment_dir`` / ``environment_name`` / ``session_id``
    / ``trial_paths`` / ``task_env_config`` (and optional
    ``keep_containers`` / ``mounts_json``).
    """

    def __init__(
        self,
        library_root: str,
        run_root: str,
        library_scope: str = "global",
        *,
        # Standard Harbor 0.6+ DockerEnvironment ctor args. Listed
        # explicitly so the merge with our extra mounts can read
        # ``trial_paths`` BEFORE delegating to ``super().__init__``.
        environment_dir: Any,
        environment_name: Any,
        session_id: Any,
        trial_paths: Any,
        task_env_config: Any,
        keep_containers: bool = False,
        mounts_json: list[Any] | None = None,
        **kwargs: Any,
    ) -> None:
        self.library_root = Path(library_root)
        self.library_scope = library_scope
        self.run_root = Path(run_root)

        # Recover task_id from trial_paths so we can build the per-trial
        # injection-context.json mount. Harbor names trial dirs as
        # ``<task_id>__<random>``; we take the prefix before the first
        # ``__``. (Falls back to the raw basename for edge cases.)
        task_id = self._extract_task_id_from_trial_paths(trial_paths)
        injection_path = (
            self.run_root / "runtime" / task_id / "injection-context.json"
        )

        # Per-env library mount source: when library_scope=="environment",
        # each env has its own subdir under library/<env_id>/. Inferred
        # from task_id prefix (e.g. "E1-LS1-T1" -> "E1"). The host-side
        # runtime's switch_env() has already lazy-init'd this LibraryStore
        # before our trial-start hook returned, so the dirs exist.
        # When library_scope=="global", the legacy single-library path
        # under library/ is used as before.
        if library_scope == "environment":
            env_id = task_id.split("-", 1)[0] if "-" in task_id else ""
            env_subdir = self.library_root / env_id if env_id else self.library_root
            self.library_active_path = env_subdir / "active"
            self.library_readonly_marker = env_subdir / ".frozen"
        else:
            self.library_active_path = self.library_root / "active"
            self.library_readonly_marker = self.library_root / ".frozen"

        # Defensive: harness creates these but a partial init could miss
        # them. Make a placeholder rather than fail container startup.
        if not injection_path.exists():
            injection_path.parent.mkdir(parents=True, exist_ok=True)
            injection_path.write_text("{}\n")
        if not self.library_active_path.exists():
            self.library_active_path.mkdir(parents=True, exist_ok=True)

        is_frozen = self.library_readonly_marker.exists()

        # Per-agent native skill folders. We don't know which agent CLI
        # will run this trial at env-construction time (Harbor instantiates
        # us before agent_config is dispatched), so we mount the SAME host
        # directory at every brand path. Each agent CLI reads from its own
        # path and ignores the others; the cost is trivial because the
        # underlying inode is shared.
        #
        # ServiceVolumeConfig schema (harbor.models.trial.config):
        #   type: "bind"|"volume"|"image"
        #   source: str
        #   target: str
        #   read_only: NotRequired[Literal[True]]   <- only set when True
        skill_targets = (
            "/root/.claude/skills",   # Claude Code
            "/root/.gemini/skills",   # Gemini CLI
            "/root/.agents/skills",   # OpenAI Codex (also Gemini/Kimi alias)
            "/root/.kimi/skills",     # Kimi CLI
            "/skills",                # legacy: PromptBuilder-injected paths
        )
        skill_mounts: list[dict[str, Any]] = []
        for target in skill_targets:
            m: dict[str, Any] = {
                "type": "bind",
                "source": str(self.library_active_path),
                "target": target,
            }
            if is_frozen:
                m["read_only"] = True
            skill_mounts.append(m)

        injection_mount: dict[str, Any] = {
            "type": "bind",
            "source": str(injection_path),
            "target": "/context/injection.json",
            "read_only": True,
        }

        merged_mounts = list(mounts_json or []) + skill_mounts + [injection_mount]

        _LOG.info(
            "GlobalLibraryEnvironment init: task_id=%s library_active=%s "
            "frozen=%s n_mounts=%d",
            task_id, self.library_active_path, is_frozen, len(merged_mounts),
        )

        super().__init__(
            environment_dir=environment_dir,
            environment_name=environment_name,
            session_id=session_id,
            trial_paths=trial_paths,
            task_env_config=task_env_config,
            keep_containers=keep_containers,
            mounts_json=merged_mounts,
            **kwargs,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_task_id_from_trial_paths(trial_paths: Any) -> str:
        """Recover the runtime-dir basename from ``trial_paths.trial_dir``.

        Harbor names each trial directory as ``<task_name>__<random7>``
        (e.g. ``E1-LS1-T1__8yFkaT4``). We strip the trailing
        ``__<random>`` segment via ``rsplit`` so that:

          * primary trials:  ``E1-LS1-T1__8yFkaT4`` -> ``E1-LS1-T1``
          * dual-T6 shadow:  ``E1-LS1-T6__oracle_shadow__7chars``
                                                   -> ``E1-LS1-T6__oracle_shadow``

        The shadow form preserves the suffix so the injection-context.json
        path -- ``runtime/<this name>/injection-context.json`` -- resolves
        to the per-trial mount file written by RuntimeBuilder, not the
        primary's. ``hooks._resolve_task`` strips the suffix again before
        looking up the canonical TaskSpec in the registry.

        Falls back to the bare basename if no ``__`` is present
        (resilience against fixtures with simpler names).
        """
        try:
            trial_dir = Path(trial_paths.trial_dir)
        except AttributeError:
            return ""
        name = trial_dir.name
        if "__" in name:
            return name.rsplit("__", 1)[0]
        return name


__all__ = ["GlobalLibraryEnvironment"]
