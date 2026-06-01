"""Runtime patches for Harbor 0.6+.

Harbor 0.6 caches ``Task.instruction`` as a plain ``str`` attribute set in
``Task.__init__`` (``models/task/task.py:56``):

    self.instruction = strip_canary(self.paths.instruction_path.read_text())

This read happens BEFORE the ``TrialEvent.START`` hook fires. Our START
hook (``RuntimeBuilder.build()`` -> ``PromptBuilder.write_*``) overwrites
``instruction.md`` on disk with a retrieval-augmented version, but
``Trial._execute_agent`` later passes the cached attribute to
``agent.run``:

    self._agent.run(instruction=self._task.instruction, ...)

So the on-disk update is silently ignored. Every Path-A / Path-B baseline
(``raw_trajectory_rag``, ``curated_*``, ``history_context_control``,
``selfgen_*``) was effectively running zero-shot -- the agents never saw
any of the retrieved skills / past-trajectory / history blocks the hook
believed it had injected. ``injection-context.json`` was a wishful audit
log.

This module monkey-patches ``Trial._execute_agent`` to re-read
``instruction.md`` from disk just before delegating to the original
implementation, so the START-hook write actually reaches the agent.

Idempotent. Apply once per process (Harbor instantiates many ``Trial``
objects but they all share the same class). Call from
``LifelongRunner.run()`` right after Harbor is first imported.
"""

from __future__ import annotations

import logging

_LOG = logging.getLogger(__name__)
_PATCHED: bool = False


def apply_harbor_patches() -> None:
    """Install runtime patches against Harbor 0.6+. Idempotent."""
    global _PATCHED
    if _PATCHED:
        return

    # Imported here, not at module top, so unit tests that don't have
    # Harbor on PYTHONPATH can still import this file.
    from harbor.models.task.task import strip_canary
    from harbor.trial.trial import Trial

    _orig_execute_agent = Trial._execute_agent

    async def _execute_agent_with_fresh_instruction(self) -> None:
        # Re-read instruction.md so START-hook injections (retrieval,
        # past-trajectory blocks, history context, etc.) actually reach
        # the agent. Without this, agent.run sees the cached string from
        # Task.__init__ -- which is the unmodified canonical instruction.
        try:
            path = getattr(getattr(self, "_task", None), "paths", None)
            if path is not None:
                instr_path = getattr(path, "instruction_path", None)
                if instr_path is not None and instr_path.exists():
                    fresh = strip_canary(instr_path.read_text())
                    self._task.instruction = fresh
        except Exception:
            _LOG.warning(
                "harbor_ext: failed to refresh task.instruction from disk; "
                "agent will see the (stale) cached version",
                exc_info=True,
            )
        await _orig_execute_agent(self)

    Trial._execute_agent = _execute_agent_with_fresh_instruction
    _PATCHED = True
    _LOG.info(
        "harbor_ext: patched Trial._execute_agent to refresh "
        "task.instruction from disk before agent.run"
    )


__all__ = ["apply_harbor_patches"]
