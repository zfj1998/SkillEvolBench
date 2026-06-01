"""``build_job_config`` -- glue from Part 1 assets to a Harbor JobConfig.

This module **hard-imports Harbor**. It runs only inside Part 9's
``LifelongRunner.run()``.

Pipeline (Engineering Design §4.3):

    benchmark/tasks/<task_slug>/   (Part 1, immutable)
        |
        | shutil.copytree (per task, before Harbor starts)
        v
    workspace/runs/<run_id>/runtime/<task_id>/harbor-task-copy/
        |
        | hook overwrite of instruction.md (per trial, in on_trial_started)
        v
    Harbor reads runtime/<task_id>/harbor-task-copy/{task.toml,instruction.md,...}

The pre-copy here ensures Harbor sees a complete task directory the moment a
trial starts. The hook then mutates only ``instruction.md`` -- everything else
(task.toml, environment/, tests/, solution/) stays byte-identical to the
benchmark asset.

The pre-copied directory is what ``GlobalLibraryEnvironment._extract_task_id``
parses ``task_id`` from -- the directory above ``harbor-task-copy`` is the
canonical ``task_id``. So the layout MUST be ``runtime/<task_id>/harbor-task-copy/``.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path
from typing import Any

# Hard imports of Harbor; module load fails when SDK is missing.
#
# Note: ``OrchestratorConfig`` was removed in newer harbor-framework
# versions; its fields (``n_concurrent_trials`` etc.) are now flattened
# onto ``JobConfig`` directly. We pass them as top-level kwargs below.
from harbor.models.environment_type import EnvironmentType
from harbor.models.job.config import JobConfig
from harbor.models.trial.config import (
    AgentConfig,
    EnvironmentConfig,
    TaskConfig,
    VerifierConfig,
)

from skillevolbench.schemas import RunConfig


_LOG = logging.getLogger(__name__)


# Map our baseline.harbor_agent_name -> the agents_port adapter import_path.
# All four adapters extend Harbor's BaseInstalledAgent and assume
# agent-runtime:latest is the base image.
_AGENT_IMPORT_PATHS: dict[str, str] = {
    "claude-code": "agents_port.preinstalled:ClaudeCodePreinstalled",
    "codex":       "agents_port.preinstalled:CodexPreinstalled",
    "gemini-cli":  "agents_port.preinstalled:GeminiCliPreinstalled",
    "kimi-cli":    "agents_port.preinstalled:KimiCliPreinstalled",
    "openclaw":    "agents_port.openclaw:OpenClaw",
}


# Suffix appended to the runtime dir + DB task_id of the second
# (oracle-retrieval) trial when ``baseline.dual_t6_retrieval`` is True.
# Exposed so hooks / env / metrics can share the exact spelling.
SHADOW_T6_SUFFIX = "__oracle_shadow"

# Suffix for within-env replay trials (``baseline.within_env_replay``).
# After each env's 30 originals, the same 30 are emitted again as
# replay TaskRecords (TaskRecord.is_replay=True); this suffix keeps
# their runtime dir + DB task_id distinct from the original.
REPLAY_SUFFIX = "__replay"


def is_shadow_path(name_or_path: str) -> bool:
    """True if a TaskConfig path/name belongs to a dual-T6 shadow trial."""
    return name_or_path.endswith(SHADOW_T6_SUFFIX)


def strip_shadow_suffix(name_or_path: str) -> str:
    """Recover the canonical task_id from a shadow path/name."""
    if name_or_path.endswith(SHADOW_T6_SUFFIX):
        return name_or_path[: -len(SHADOW_T6_SUFFIX)]
    return name_or_path


def is_replay_path(name_or_path: str) -> bool:
    """True if a TaskConfig path/name belongs to a within-env replay trial."""
    return name_or_path.endswith(REPLAY_SUFFIX)


def strip_replay_suffix(name_or_path: str) -> str:
    """Recover the canonical task_id from a replay path/name."""
    if name_or_path.endswith(REPLAY_SUFFIX):
        return name_or_path[: -len(REPLAY_SUFFIX)]
    return name_or_path


def build_job_config(
    config: RunConfig,
    ordered_task_records: list[Any],
) -> JobConfig:
    """Construct a Harbor ``JobConfig`` from a fully-validated ``RunConfig``.

    Parameters
    ----------
    config
        The Part-3-validated run config. Drives orchestrator type, agent
        selection, and library-mount paths.
    ordered_task_records
        List of ``TaskRecord`` objects from ``TaskRegistry`` already in
        global execution order (Part 9 ``scheduler.py``). Each record's
        ``folder`` field points at the immutable ``benchmark/tasks/<slug>/``
        directory; we pre-copy each into ``runtime/<task_id>/harbor-task-copy/``.

    Returns
    -------
    Harbor ``JobConfig`` ready to feed into ``harbor.Job(config=...)``.
    """
    run_dir = config.run_dir
    run_dir.mkdir(parents=True, exist_ok=True)
    runtime_root = run_dir / "runtime"
    runtime_root.mkdir(exist_ok=True)
    # ``library_root`` is the parent dir; env.py computes per-env subdirs
    # (library/<env_id>/active and library/<env_id>/.frozen) when
    # ``library_scope=="environment"``, otherwise uses library/active and
    # library/.frozen as before. This keeps the kwargs compact -- env.py
    # has the per-trial task_id from trial_paths to derive the env_id.
    library_root = run_dir / "library"

    # ---- 1. Pre-copy 180 task skeletons ----
    # Layout: ``runtime/<task_id>/{task.toml, instruction.md, ...}``.
    # We do NOT add a "harbor-task-copy" subdirectory anymore: Harbor 0.6+
    # rejects ``TaskConfig(path=..., name=...)`` ("Cannot set both") and
    # auto-derives ``name`` from the path basename. Putting files directly
    # under the ``<task_id>/`` directory makes that basename equal to the
    # task_id, which is what hooks use to look up the TaskRecord.
    dual_t6 = bool(getattr(config.baseline, "dual_t6_retrieval", False))

    task_configs: list[TaskConfig] = []
    for record in ordered_task_records:
        # Replay records share the source folder with the original
        # (same task content) but get a __replay-suffixed runtime dir
        # + DB task_id so they don't collide with the original record.
        # Hooks detect the suffix and skip mutating logic.
        task_id_for_runtime = record.spec.task_id
        if record.is_replay:
            task_id_for_runtime = f"{task_id_for_runtime}{REPLAY_SUFFIX}"
        runtime_task_dir = runtime_root / task_id_for_runtime
        _copy_task_skeleton(src=record.folder, dst=runtime_task_dir)
        # Note: ``source`` left at its default (None). Harbor's
        # ``_update_metric_display`` does ``dataset_name = task.source or "adhoc"``
        # and looks up ``self._metrics[dataset_name]``. ``_resolve_metrics``
        # only ever populates the "adhoc" key for path-based tasks, so
        # passing a custom source name (e.g. "skillevolbench-runtime")
        # leaves us with an unpopulated entry and the trial-end hook
        # crashes with ``IndexError: list index out of range`` when it
        # tries ``self._metrics[dataset_name][0].compute(rewards)``.
        task_configs.append(
            TaskConfig(path=str(runtime_task_dir))
        )

        # Dual-T6: for every composition (T6) task, immediately schedule
        # a SHADOW trial that uses OracleRetriever. Library is frozen at
        # T4-T6, so scheduling the shadow right after the primary keeps
        # both trials seeing the identical library state -- the comparison
        # is paired-by-trial.
        if dual_t6 and record.spec.role.value == "composition":
            shadow_task_id = f"{record.spec.task_id}{SHADOW_T6_SUFFIX}"
            shadow_task_dir = runtime_root / shadow_task_id
            _copy_task_skeleton(src=record.folder, dst=shadow_task_dir)
            task_configs.append(
                TaskConfig(path=str(shadow_task_dir))
            )

    # ---- 2. Resolve agent adapter ----
    agent_name = config.baseline.harbor_agent_name
    agent_import_path = _AGENT_IMPORT_PATHS.get(agent_name)
    if agent_import_path is None:
        # Fall back to letting Harbor resolve by name (its default registry).
        _LOG.warning(
            "harbor_agent_name=%r is not in agents_port; relying on Harbor's "
            "default agent registry. Consider adding it to "
            "_AGENT_IMPORT_PATHS in job_builder.py.",
            agent_name,
        )

    agent_kwargs: dict[str, Any] = {**config.baseline.agent_kwargs}
    if config.api_base:
        agent_kwargs.setdefault("api_base", config.api_base)

    if agent_import_path is not None:
        # Harbor's AgentFactory prioritizes a recognized ``name`` over
        # ``import_path``. Omit name here so our preinstalled adapters run.
        agent_cfg_kwargs: dict[str, Any] = {
            "import_path": agent_import_path,
            "model_name": config.baseline.model_name,
            "kwargs": agent_kwargs,
        }
    else:
        agent_cfg_kwargs = {
            "name": agent_name,
            "model_name": config.baseline.model_name,
            "kwargs": agent_kwargs,
        }

    # ---- 3. Build JobConfig ----
    return JobConfig(
        job_name=config.run_id,
        jobs_dir=str(run_dir / "harbor-job"),
        tasks=task_configs,
        datasets=[],   # explicit task list -- no dataset auto-expansion.
        agents=[AgentConfig(**agent_cfg_kwargs)],
        environment=EnvironmentConfig(
            type=EnvironmentType.DOCKER,
            import_path="skillevolbench.harbor_ext.env:GlobalLibraryEnvironment",
            kwargs={
                "library_root": str(library_root),
                "library_scope": getattr(config.baseline, "library_scope", "global"),
                "run_root": str(run_dir),
            },
        ),
        # Harbor 0.6+ renamed ``timeout_sec`` -> ``override_timeout_sec``;
        # there's also ``max_timeout_sec`` for an upper-bound cap.
        verifier=VerifierConfig(override_timeout_sec=300.0),
        # Flattened from the removed OrchestratorConfig: pass orchestrator
        # fields directly to JobConfig.
        n_concurrent_trials=config.harbor_n_concurrent_trials,  # ★ must be 1
        n_attempts=1,
        # ``artifacts`` is a flat list of container paths Harbor will copy
        # to ``<trial_dir>/artifacts/<basename>`` after the trial. Note:
        # ``/logs/agent/`` and ``/logs/verifier/`` are ALREADY bind-mounted
        # back to the host, so explicit artifact declaration just produces
        # a duplicate copy. We keep ``trajectory.json`` here as a belt-and-
        # suspenders hedge (in case the mount is unexpectedly lost) -- the
        # VerifierAdapter probes both ``<trial>/agent/`` and
        # ``<trial>/artifacts/`` so either copy works.
        #
        # IMPORTANT: do NOT list ``/context/injection.json`` here. It's
        # mounted ``read_only=True`` (env.py), so Harbor's
        # ``download_file`` -> ``_chown_to_host_user`` chown step fails
        # every trial with "Read-only file system", emitting a benign
        # but noisy ``Failed to download artifact ... (best-effort)``
        # warning + a ``status: "failed"`` manifest entry. The file is
        # already on host as ``<run_root>/runtime/<task_id>/
        # injection-context.json`` (RuntimeBuilder writes it directly),
        # so archiving it is pure redundancy.
        artifacts=[
            "/logs/agent/trajectory.json",
        ],
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _copy_task_skeleton(src: Path, dst: Path) -> None:
    """Mirror ``benchmark/tasks/<slug>/`` -> ``runtime/<task_id>/harbor-task-copy/``.

    The copy is full and replaces any existing directory so a resume run
    doesn't see stale artifacts. ``instruction.md`` is included in the copy
    but will be overwritten by the hook in ``on_trial_started`` before
    Harbor's agent reads it.
    """
    if dst.exists():
        shutil.rmtree(dst)
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(src, dst)


__all__ = [
    "build_job_config",
    "_AGENT_IMPORT_PATHS",  # exposed for testing / introspection
]
