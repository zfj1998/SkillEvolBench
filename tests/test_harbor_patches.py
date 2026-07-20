from __future__ import annotations

import asyncio
import contextlib
import json
import logging
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest

from skillevolbench.harbor_ext import _patches


def _install_fake_harbor(
    monkeypatch: pytest.MonkeyPatch,
    trial_class: type,
    *,
    single_step_class: type | None = None,
    version: str = "0.20.0",
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
            "harbor.trial.single_step",
        )
    }
    modules["harbor.models.task.task"].strip_canary = lambda text: text.removeprefix(
        "# canary\n"
    )
    modules["harbor"].__version__ = version
    modules["harbor.trial.trial"].Trial = trial_class

    class FakeSingleStepTrial:
        async def _run_verifier(self) -> None:
            self.events.append("verifier")

    modules["harbor.trial.single_step"].SingleStepTrial = (
        single_step_class or FakeSingleStepTrial
    )
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.setattr(_patches, "_PATCHED", False)
    monkeypatch.setattr(_patches, "_POST_VERIFIER_PATCHED", False)
    monkeypatch.setattr(_patches, "_POST_VERIFIER_CALLBACK", None)


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


def test_modern_resume_preserves_followup_instruction(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    instruction_path = tmp_path / "instruction.md"
    instruction_path.write_text("original task prompt")

    class ModernTrial:
        async def _run_agent_phase(self, *args: Any, **kwargs: Any) -> None:
            self.seen_instruction = kwargs["instruction"]

    _install_fake_harbor(monkeypatch, ModernTrial)
    _patches.apply_harbor_patches()

    trial = ModernTrial()
    trial.task = _task(instruction_path)
    asyncio.run(
        trial._run_agent_phase(
            target=object(),
            instruction="post-verifier reflection prompt",
            timeout_sec=10,
            user=None,
            resume=True,
        )
    )

    assert trial.seen_instruction == "post-verifier reflection prompt"
    assert trial.task.instruction == "stale"


def _exact_trial_classes() -> tuple[type, type]:
    class ExactTrial:
        async def _run_agent_phase(
            self,
            *,
            target: Any,
            instruction: str,
            timeout_sec: float | None,
            user: str | int | None,
            step_cfg: Any = None,
            resume: bool = False,
        ) -> None:
            del target, instruction, timeout_sec, user, step_cfg, resume

        async def _upload_agent_logs(self) -> None:
            self.events.append("upload-agent-logs")

        async def _separate_verifier_env(
            self,
            env_config: Any,
            *,
            key: str,
            plan: Any,
            step_cfg: Any = None,
        ) -> None:
            del env_config, key, plan, step_cfg

        async def _stop_agent_environment(self) -> None:
            self.events.append("harbor-cleanup")

        def _network_plan(
            self,
            step_cfg: Any = None,
            *,
            env_config: Any = None,
        ) -> Any:
            del step_cfg, env_config
            return None

        @contextlib.asynccontextmanager
        async def _phase_network_policy(
            self,
            environment: Any,
            *,
            baseline_policy: Any,
            phase_policy: Any,
        ) -> Any:
            del environment, baseline_policy, phase_policy
            yield

        def _log_context(
            self,
            phase: Any,
            environment: Any,
            step_name: Any = None,
        ) -> Any:
            del phase, environment, step_name
            return contextlib.nullcontext()

        async def _emit(self, event: Any) -> None:
            del event

    class ExactSingleStepTrial(ExactTrial):
        async def _run(self) -> None:
            self.events.append("stock-run")

        async def _run_agent(self) -> None:
            self.events.append("agent")

        async def _collect_artifacts(
            self, *, stop_main_before_sidecars: bool = False
        ) -> None:
            assert stop_main_before_sidecars is False
            self.events.append("collect")
            snapshot = self.paths.artifacts_dir / "root" / "task"
            snapshot.mkdir(parents=True)
            (snapshot / "answer.txt").write_text("immutable solve output")
            (self.paths.artifacts_dir / "manifest.json").write_text(
                json.dumps(
                    [
                        {
                            "source": "/root/task",
                            "destination": "artifacts/root/task",
                            "type": "directory",
                            "status": "ok",
                            "service": None,
                        }
                    ]
                )
            )

    return ExactTrial, ExactSingleStepTrial


class _FakeAgentEnvironment:
    def __init__(self, events: list[str]) -> None:
        self.events = events
        self.running = True

    async def main_service_identity(self) -> str:
        return "container-123"

    async def main_service_running_identity(self) -> str:
        return "container-123" if self.running else ""

    async def stop_service(self, service: str) -> None:
        assert service == "main"
        self.events.append("stop-main")
        self.running = False


def test_post_verifier_lifecycle_validates_snapshot_and_cleans_up(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_trial, exact_single_step = _exact_trial_classes()
    _install_fake_harbor(
        monkeypatch,
        exact_trial,
        single_step_class=exact_single_step,
    )

    async def isolated_verifier(trial: Any) -> None:
        assert trial._sevb_task_snapshot_path.is_dir()
        trial.events.append("verifier")

    monkeypatch.setattr(_patches, "_run_isolated_verifier", isolated_verifier)
    _patches.apply_harbor_patches()

    async def callback(trial: Any) -> None:
        trial.events.append("reflection")

    _patches.register_post_verifier_callback(callback)
    trial = exact_single_step()
    trial.events = []
    trial.agent_environment = _FakeAgentEnvironment(trial.events)
    trial.paths = SimpleNamespace(artifacts_dir=tmp_path / "artifacts")
    trial.task = SimpleNamespace(
        has_steps=False,
        config=SimpleNamespace(artifacts=[]),
    )
    trial.config = SimpleNamespace(artifacts=["/root/task"])
    trial.logger = logging.getLogger("test-harbor-patches")

    asyncio.run(trial._run())
    _patches.clear_post_verifier_callback()

    assert trial._sevb_agent_container_identity == "container-123"
    assert trial._sevb_agent_main_stopped is True
    assert trial._sevb_task_snapshot_path == tmp_path / "artifacts/root/task"
    assert trial.events[:6] == [
        "agent",
        "upload-agent-logs",
        "stop-main",
        "collect",
        "verifier",
        "reflection",
    ]
    assert trial.events[-3:] == ["stop-main", "harbor-cleanup", "stop-main"]


def test_private_api_rejects_wrong_harbor_version(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_trial, exact_single_step = _exact_trial_classes()
    _install_fake_harbor(
        monkeypatch,
        exact_trial,
        single_step_class=exact_single_step,
        version="0.20.1",
    )

    with pytest.raises(RuntimeError, match="expected harbor==0.20.0"):
        _patches.apply_harbor_patches()
    assert _patches._PATCHED is False


def test_private_api_rejects_signature_drift(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    exact_trial, exact_single_step = _exact_trial_classes()

    async def drifted_collect(self: Any, stop_main_before_sidecars: bool = False) -> None:
        del self, stop_main_before_sidecars

    exact_single_step._collect_artifacts = drifted_collect
    _install_fake_harbor(
        monkeypatch,
        exact_trial,
        single_step_class=exact_single_step,
    )

    with pytest.raises(RuntimeError, match="private API signatures changed"):
        _patches.apply_harbor_patches()
    assert _patches._PATCHED is False


@pytest.mark.parametrize(
    ("manifest", "make_snapshot", "error"),
    [
        (None, True, "readable artifacts/manifest"),
        ({"entries": []}, True, "JSON list"),
        ([], True, "exactly one /root/task"),
        (
            [
                {
                    "source": "/root/task",
                    "destination": "artifacts/root/task",
                    "type": "directory",
                    "status": "failed",
                    "service": None,
                }
            ],
            True,
            "status='failed'",
        ),
        (
            [
                {
                    "source": "/root/task",
                    "destination": "artifacts/root/task",
                    "type": "directory",
                    "status": "ok",
                    "service": None,
                },
                {
                    "source": "/root/task",
                    "destination": "artifacts/root/task-copy",
                    "type": "directory",
                    "status": "ok",
                    "service": None,
                },
            ],
            True,
            "found 2",
        ),
        (
            [
                {
                    "source": "/root/task",
                    "destination": "artifacts/root/task",
                    "type": "directory",
                    "status": "ok",
                    "service": None,
                }
            ],
            False,
            "missing or not a real directory",
        ),
    ],
)
def test_task_snapshot_validation_fails_closed(
    tmp_path: Path,
    manifest: Any,
    make_snapshot: bool,
    error: str,
) -> None:
    artifacts_dir = tmp_path / "artifacts"
    artifacts_dir.mkdir()
    if manifest is not None:
        (artifacts_dir / "manifest.json").write_text(json.dumps(manifest))
    if make_snapshot:
        snapshot = artifacts_dir / "root" / "task"
        snapshot.mkdir(parents=True)
        (snapshot / "answer.txt").write_text("answer")
    trial = SimpleNamespace(paths=SimpleNamespace(artifacts_dir=artifacts_dir))

    with pytest.raises(RuntimeError, match=error):
        _patches._validate_task_snapshot(trial)
    assert not hasattr(trial, "_sevb_task_snapshot_path")


def test_task_snapshot_validation_rejects_empty_directory(tmp_path: Path) -> None:
    artifacts_dir = tmp_path / "artifacts"
    snapshot = artifacts_dir / "root" / "task"
    snapshot.mkdir(parents=True)
    (artifacts_dir / "manifest.json").write_text(
        json.dumps(
            [
                {
                    "source": "/root/task",
                    "destination": "artifacts/root/task",
                    "type": "directory",
                    "status": "ok",
                    "service": None,
                }
            ]
        )
    )
    trial = SimpleNamespace(paths=SimpleNamespace(artifacts_dir=artifacts_dir))

    with pytest.raises(RuntimeError, match="snapshot is empty"):
        _patches._validate_task_snapshot(trial)


def test_cleanup_fails_if_harbor_swallow_leaves_main_running() -> None:
    class Environment:
        async def stop_service(self, service: str) -> None:
            assert service == "main"

        async def main_service_running_identity(self) -> str:
            return "still-running"

    class Trial:
        agent_environment = Environment()
        logger = logging.getLogger("test-harbor-cleanup")

        async def _stop_agent_environment(self) -> None:
            # Models Harbor 0.20's best-effort method returning after it has
            # recorded/swallowed a provider cleanup failure.
            return None

    with pytest.raises(RuntimeError, match="could not prove"):
        asyncio.run(_patches._secure_stop_agent_environment(Trial()))


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
