from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from skillevolbench.harbor_ext import _patches


def _install_fake_harbor(
    monkeypatch: pytest.MonkeyPatch,
    trial_class: type,
) -> None:
    modules = {
        name: ModuleType(name)
        for name in (
            "harbor",
            "harbor.models",
            "harbor.models.task",
            "harbor.models.task.task",
            "harbor.trial",
            "harbor.trial.trial",
        )
    }
    modules["harbor.models.task.task"].strip_canary = lambda text: text.removeprefix(
        "# canary\n"
    )
    modules["harbor.trial.trial"].Trial = trial_class
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(_patches, "_PATCHED", False)


def _task(instruction_path: Path, *, cached: str = "stale") -> SimpleNamespace:
    return SimpleNamespace(
        has_steps=False,
        instruction=cached,
        paths=SimpleNamespace(instruction_path=instruction_path),
    )


def test_legacy_execute_agent_refreshes_underscore_task(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction_path = tmp_path / "instruction.md"
    instruction_path.write_text("# canary\ninjected legacy prompt")

    class LegacyTrial:
        async def _execute_agent(self) -> None:
            self.seen_instruction = self._task.instruction

    _install_fake_harbor(monkeypatch, LegacyTrial)
    _patches.apply_harbor_patches()
    patched_method = LegacyTrial._execute_agent
    _patches.apply_harbor_patches()

    trial = LegacyTrial()
    trial._task = _task(instruction_path)
    asyncio.run(trial._execute_agent())

    assert LegacyTrial._execute_agent is patched_method
    assert trial.seen_instruction == "injected legacy prompt"
    assert trial._task.instruction == "injected legacy prompt"


def test_modern_agent_phase_replaces_single_step_instruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction_path = tmp_path / "instruction.md"
    instruction_path.write_text("# canary\ninjected modern prompt")

    class ModernTrial:
        async def _run_agent_phase(self, *args: Any, **kwargs: Any) -> None:
            self.seen_args = args
            self.seen_kwargs = kwargs

    _install_fake_harbor(monkeypatch, ModernTrial)
    _patches.apply_harbor_patches()

    trial = ModernTrial()
    trial.task = _task(instruction_path)
    asyncio.run(
        trial._run_agent_phase(
            target=object(),
            instruction="stale",
            timeout_sec=10,
            user=None,
        )
    )

    assert trial.seen_args == ()
    assert trial.seen_kwargs["instruction"] == "injected modern prompt"
    assert trial.task.instruction == "injected modern prompt"


def test_modern_agent_phase_leaves_multi_step_instruction_unchanged(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction_path = tmp_path / "instruction.md"
    instruction_path.write_text("injected single-step prompt")

    class ModernTrial:
        async def _run_agent_phase(self, *args: Any, **kwargs: Any) -> None:
            self.seen_kwargs = kwargs

    _install_fake_harbor(monkeypatch, ModernTrial)
    _patches.apply_harbor_patches()

    trial = ModernTrial()
    trial.task = _task(instruction_path)
    trial.task.has_steps = True
    asyncio.run(
        trial._run_agent_phase(
            target=object(),
            instruction="step-specific prompt",
            timeout_sec=10,
            user=None,
        )
    )

    assert trial.seen_kwargs["instruction"] == "step-specific prompt"
    assert trial.task.instruction == "stale"


def test_refresh_preserves_harbor_extra_instructions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction_path = tmp_path / "instruction.md"
    instruction_path.write_text("injected prompt")

    class ModernTrial:
        async def _run_agent_phase(self, *args: Any, **kwargs: Any) -> None:
            self.seen_instruction = kwargs["instruction"]

    _install_fake_harbor(monkeypatch, ModernTrial)
    _patches.apply_harbor_patches()

    trial = ModernTrial()
    trial.task = _task(instruction_path)
    trial.task._append_extra_instructions = lambda text: f"{text}\n\nextra"
    asyncio.run(
        trial._run_agent_phase(
            target=object(), instruction="stale", timeout_sec=10, user=None
        )
    )

    assert trial.seen_instruction == "injected prompt\n\nextra"


def test_missing_instruction_fails_closed_before_agent_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class ModernTrial:
        async def _run_agent_phase(self, *args: Any, **kwargs: Any) -> None:
            self.agent_ran = True

    _install_fake_harbor(monkeypatch, ModernTrial)
    _patches.apply_harbor_patches()

    trial = ModernTrial()
    trial.agent_ran = False
    trial.task = _task(tmp_path / "missing-instruction.md")

    with pytest.raises(RuntimeError, match="refusing to run"):
        asyncio.run(
            trial._run_agent_phase(
                target=object(), instruction="stale", timeout_sec=10, user=None
            )
        )
    assert trial.agent_ran is False


def test_unknown_trial_api_fails_with_actionable_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class UnknownTrial:
        pass

    _install_fake_harbor(monkeypatch, UnknownTrial)

    with pytest.raises(RuntimeError, match="Unsupported Harbor Trial API"):
        _patches.apply_harbor_patches()
