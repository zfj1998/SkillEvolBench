"""Runtime compatibility patches for Harbor instruction injection.

Harbor reads ``instruction.md`` while constructing a ``Task``, before the
``TrialEvent.START`` hook fires.  SkillEvolBench's START hook then writes the
retrieval-augmented instruction to disk, so Harbor's cached instruction must
be refreshed immediately before agent execution.

The private execution API changed across supported Harbor releases:

* older releases execute through ``Trial._execute_agent`` and store the task
  on ``self._task``;
* Harbor 0.7+ executes through ``Trial._run_agent_phase``; newer releases
  store the task on ``self.task`` instead of ``self._task``.

``apply_harbor_patches`` detects the available API instead of assuming one
version.  Multi-step calls are deliberately left untouched: their per-step
instructions are read separately, and SkillEvolBench currently contains only
single-step tasks.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any


_LOG = logging.getLogger(__name__)
_PATCHED: bool = False


def _refresh_instruction(self: Any, strip_canary: Callable[[str], str]) -> str | None:
    """Refresh and return a trial's cached single-step instruction."""
    task = getattr(self, "task", None)
    if task is None:
        task = getattr(self, "_task", None)
    if task is None:
        raise RuntimeError("Harbor trial does not expose task or _task")
    if getattr(task, "has_steps", False):
        return None

    paths = getattr(task, "paths", None)
    instruction_path = getattr(paths, "instruction_path", None)
    if instruction_path is None:
        raise RuntimeError("Harbor task does not expose paths.instruction_path")
    if not instruction_path.is_file():
        raise FileNotFoundError(
            f"Harbor instruction file disappeared before agent execution: "
            f"{instruction_path}"
        )

    fresh = strip_canary(instruction_path.read_text())
    append_extra = getattr(task, "_append_extra_instructions", None)
    if callable(append_extra):
        fresh = append_extra(fresh)
    task.instruction = fresh
    return fresh


def apply_harbor_patches() -> None:
    """Install the instruction-refresh patch once for a Harbor process."""
    global _PATCHED
    if _PATCHED:
        return

    # Keep Harbor optional at module import time so the rest of the benchmark
    # remains unit-testable without the SDK installed.
    from harbor.models.task.task import strip_canary
    from harbor.trial.trial import Trial

    if hasattr(Trial, "_run_agent_phase"):
        # Harbor 0.7+ passes the cached instruction as a keyword argument.
        # ``_refresh_instruction`` checks Task.has_steps rather than relying on
        # the newer ``step_cfg`` parameter, which did not exist in Harbor 0.7.
        original_run_agent_phase = Trial._run_agent_phase

        async def _run_agent_phase_with_fresh_instruction(
            self: Any, *args: Any, **kwargs: Any
        ) -> None:
            try:
                fresh = _refresh_instruction(self, strip_canary)
                if fresh is not None:
                    if "instruction" not in kwargs:
                        raise RuntimeError(
                            "Harbor _run_agent_phase did not receive instruction "
                            "as a keyword argument"
                        )
                    kwargs["instruction"] = fresh
            except Exception as exc:
                raise RuntimeError(
                    "Harbor instruction refresh failed; refusing to run the "
                    "agent with a stale pre-hook prompt"
                ) from exc
            await original_run_agent_phase(self, *args, **kwargs)

        Trial._run_agent_phase = _run_agent_phase_with_fresh_instruction
        patched_api = "Trial._run_agent_phase"

    elif hasattr(Trial, "_execute_agent"):
        # Legacy Harbor path.  Refreshing ``self._task.instruction`` is enough
        # because the original method reads that attribute after this wrapper.
        original_execute_agent = Trial._execute_agent

        async def _execute_agent_with_fresh_instruction(self: Any) -> None:
            try:
                _refresh_instruction(self, strip_canary)
            except Exception as exc:
                raise RuntimeError(
                    "Harbor instruction refresh failed; refusing to run the "
                    "agent with a stale pre-hook prompt"
                ) from exc
            await original_execute_agent(self)

        Trial._execute_agent = _execute_agent_with_fresh_instruction
        patched_api = "Trial._execute_agent"

    else:
        raise RuntimeError(
            "Unsupported Harbor Trial API: expected _execute_agent or "
            "_run_agent_phase. Pin a supported Harbor revision or update "
            "skillevolbench.harbor_ext._patches."
        )

    _PATCHED = True
    _LOG.info(
        "harbor_ext: patched %s to refresh task.instruction before agent.run",
        patched_api,
    )


__all__ = ["apply_harbor_patches"]
