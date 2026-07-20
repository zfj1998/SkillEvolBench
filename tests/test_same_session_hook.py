from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.components.verifier_adapter import UnscoreableTrialError
from skillevolbench.harbor_ext.hooks import SkillEvolBenchHooks
from skillevolbench.schemas import TrialOutcome


SESSION_ID = "ses-1"
TASK = SimpleNamespace(
    task_id="E1-LS1-T1",
    family_id="E1-LS1",
    primary_skill="E1-LS1.systematic-error-diagnosis",
    latent_skill_id="E1-LS1.systematic-error-diagnosis",
    role="canonical",
    environment_id="E1",
    phase="learning",
)


def _export_message(role: str, text: str) -> dict:
    return {
        "info": {"role": role, "sessionID": SESSION_ID},
        "parts": [{"type": "text", "text": text, "sessionID": SESSION_ID}],
    }


def _solve_export() -> dict:
    return {
        "info": {"id": SESSION_ID},
        "messages": [
            _export_message("user", "solve prompt"),
            _export_message("assistant", "solve answer"),
        ],
    }


def _trajectory(messages: list[tuple[str, str]]) -> dict:
    return {
        "schema_version": "ATIF-v1.7",
        "session_id": SESSION_ID,
        "agent": {"name": "opencode", "version": "1.18.3"},
        "steps": [
            {
                "step_id": index,
                "source": source,
                "message": message,
            }
            for index, (source, message) in enumerate(messages, start=1)
        ],
        "final_metrics": {},
    }


class _Library:
    def has_seed_for(self, _family_id: str) -> bool:
        return False

    def skills_in_family(self, _family_id: str):
        return []


class _Events:
    def __init__(self) -> None:
        self.items: list[tuple[str, dict]] = []

    def record(self, event_type: str, payload: dict) -> None:
        self.items.append((event_type, payload))


class _Environment:
    def __init__(self, task_dir: Path) -> None:
        self.capabilities = SimpleNamespace(mounted=True)
        self.task_dir = task_dir
        self.empty_calls: list[tuple[list[str], bool]] = []
        self.running = False
        self.refuse_stop = False
        self.stop_calls = 0

    async def empty_dirs(self, paths, chmod=False) -> None:
        self.empty_calls.append((list(paths), chmod))

    async def restart_main_service(self) -> None:
        self.running = True

    async def main_service_identity(self) -> str:
        return "container-1"

    async def main_service_running_identity(self) -> str:
        return "container-1" if self.running else ""

    async def run_healthcheck(self) -> None:
        assert self.running

    async def stop_service(self, service: str) -> None:
        assert service == "main"
        self.stop_calls += 1
        if not self.refuse_stop:
            self.running = False

    async def service_download_dir(
        self, source_dir: str, target_dir: Path, *, service: str
    ) -> None:
        assert source_dir == "/root/task"
        assert service == "main"
        assert not self.running
        shutil.copytree(self.task_dir, target_dir, dirs_exist_ok=True)


class _Agent:
    def __init__(self, trial: "_Trial") -> None:
        self.trial = trial
        self.opencode_session_id = SESSION_ID

    def populate_context_post_run(self, context) -> None:
        assert not self.trial.agent_environment.running
        export = json.loads(
            (self.trial.paths.agent_dir / "opencode.session.json").read_text()
        )
        steps: list[tuple[str, str]] = []
        for message in export["messages"]:
            role = message["info"]["role"]
            source = "user" if role == "user" else "agent"
            steps.append((source, message["parts"][0]["text"]))
        (self.trial.paths.agent_dir / "trajectory.json").write_text(
            json.dumps(_trajectory(steps))
        )
        context.cost_usd = 0.0
        context.n_input_tokens = 10
        context.n_output_tokens = 2
        context.n_cache_tokens = 0


class _Trial:
    def __init__(
        self,
        root: Path,
        *,
        mutate_task: bool = False,
        bad_prefix: bool = False,
        candidate_kind: str = "valid",
    ) -> None:
        self.paths = SimpleNamespace(
            trial_dir=root,
            agent_dir=root / "agent",
            verifier_dir=root / "verifier",
            artifacts_dir=root / "artifacts",
        )
        self.paths.agent_dir.mkdir(parents=True)
        self.paths.verifier_dir.mkdir()
        (self.paths.verifier_dir / "reward.txt").write_text("0.0\n")
        (self.paths.verifier_dir / "hidden-detail.json").write_text(
            '{"secret": true}'
        )
        self.task_workspace = root / "container-task"
        self.task_workspace.mkdir()
        (self.task_workspace / "answer.txt").write_text("solve state\n")
        task_snapshot = self.paths.artifacts_dir / "root" / "task"
        task_snapshot.mkdir(parents=True)
        (task_snapshot / "answer.txt").write_text("solve state\n")
        (self.paths.agent_dir / "trajectory.json").write_text(
            json.dumps(
                _trajectory(
                    [("user", "solve prompt"), ("agent", "solve answer")]
                )
            )
        )
        (self.paths.agent_dir / "opencode.session.json").write_text(
            json.dumps(_solve_export())
        )
        (self.paths.agent_dir / "opencode.solve.jsonl").write_text(
            json.dumps({"type": "text", "sessionID": SESSION_ID}) + "\n"
        )

        self.task = SimpleNamespace(
            name=TASK.task_id,
            config=SimpleNamespace(agent=SimpleNamespace(user=None)),
        )
        self.config = SimpleNamespace()
        self.result = SimpleNamespace(agent_result=None)
        self.agent_environment = _Environment(self.task_workspace)
        self.agent = _Agent(self)
        self.agent_env_paths = SimpleNamespace(tests_dir="/tests")
        self._agent_timeout_sec = 60
        self._is_agent_environment_stopped = False
        self._sevb_agent_main_stopped = True
        self._sevb_agent_container_identity = "container-1"
        self.verifier_was_hidden_during_resume = False
        self.verifier_was_hidden_at_cleanup = False
        self.mutate_task = mutate_task
        self.bad_prefix = bad_prefix
        self.candidate_kind = candidate_kind
        self.outside_candidate = root / "outside-candidate.json"

    async def _run_agent_phase(self, *, target, instruction, resume, **_kwargs):
        assert resume is True
        assert self.agent_environment.running
        assert "official verifier" in instruction
        self.verifier_was_hidden_during_resume = not any(
            self.paths.verifier_dir.iterdir()
        )
        solve_messages = list(_solve_export()["messages"])
        if self.bad_prefix:
            solve_messages[1] = _export_message("assistant", "tampered solve")
        solve_messages.extend(
            [
                _export_message("user", instruction),
                _export_message("assistant", "encoded a reusable lesson"),
            ]
        )
        (self.paths.agent_dir / "opencode.session.json").write_text(
            json.dumps({"info": {"id": SESSION_ID}, "messages": solve_messages})
        )
        (self.paths.agent_dir / "opencode.reflection.jsonl").write_text(
            json.dumps({"type": "text", "sessionID": SESSION_ID}) + "\n"
        )
        if self.mutate_task:
            (self.task_workspace / "answer.txt").write_text("reflection mutation\n")

        slug = "systematic-error-diagnosis"
        skill_md = (
            "---\n"
            f"name: {slug}\n"
            "description: Use when diagnosing a concrete runtime failure.\n"
            "---\n\n# Workflow\n\nInspect, isolate, fix, validate.\n"
        )
        candidate = {
            "summary": "distill diagnosis",
            "operation_type": "create",
            "upsert_files": {f"{slug}/SKILL.md": skill_md},
            "delete_paths": [],
        }
        candidate_path = self.paths.agent_dir / "self_reflection_patch.json"
        if self.candidate_kind == "symlink":
            self.outside_candidate.write_text(json.dumps(candidate))
            candidate_path.symlink_to(self.outside_candidate)
        elif self.candidate_kind == "secret":
            candidate["summary"] = "secret=" + "unit-test-secret"
            candidate_path.write_text(json.dumps(candidate))
        else:
            candidate_path.write_text(json.dumps(candidate))

        target.agent_result = SimpleNamespace(
            cost_usd=None,
            n_input_tokens=0,
            n_output_tokens=0,
            n_cache_tokens=0,
        )

    async def _stop_agent_environment(self) -> None:
        self.verifier_was_hidden_at_cleanup = not any(
            self.paths.verifier_dir.iterdir()
        )
        if not self.agent_environment.refuse_stop:
            self.agent_environment.running = False
        self._is_agent_environment_stopped = True


def _build(tmp_path: Path, **trial_kwargs):
    baseline = load_baseline("selfgen_in_session_always")
    outcome = TrialOutcome(
        task_id=TASK.task_id,
        verifier_passed=False,
        reward=0.0,
        trajectory_path=tmp_path / "agent" / "trajectory.json",
    )
    events = _Events()
    runtime = SimpleNamespace(
        baseline=baseline,
        library=_Library(),
        verifier_adapter=SimpleNamespace(parse=lambda _result: outcome),
        event_store=events,
    )
    registry = SimpleNamespace(task=lambda _task_id: SimpleNamespace(spec=TASK))
    hooks = SkillEvolBenchHooks(runtime, registry, None, None)  # type: ignore[arg-type]
    trial = _Trial(tmp_path, **trial_kwargs)
    return hooks, trial, events


def test_post_verifier_resume_is_host_audited_and_continuous(
    tmp_path: Path,
) -> None:
    hooks, trial, events = _build(tmp_path)

    asyncio.run(hooks.on_post_verifier(trial))

    assert trial.verifier_was_hidden_during_resume is True
    assert trial.verifier_was_hidden_at_cleanup is True
    assert trial._is_agent_environment_stopped is True
    assert trial.agent_environment.empty_calls == [(["/tests"], False)]
    assert trial.agent_environment.stop_calls == 1
    assert (trial.paths.verifier_dir / "reward.txt").read_text() == "0.0\n"
    assert (trial.paths.verifier_dir / "hidden-detail.json").is_file()

    audit = tmp_path / "self-reflection-audit"
    assert (audit / "official-verifier" / "reward.txt").read_text() == "0.0\n"
    assert (audit / "trajectory.solve.json").is_file()
    assert (audit / "trajectory.full.json").is_file()
    assert (audit / "opencode.session.solve.json").is_file()
    assert (audit / "opencode.session.full.json").is_file()
    assert (audit / "self_reflection_prompt.md").is_file()
    assert (audit / "self_reflection_feedback.json").is_file()
    assert (audit / "self_reflection_result.json").is_file()
    assert (audit / "self_reflection_patch.json").is_file()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert not (trial.paths.agent_dir / "self_reflection_prompt.md").exists()

    record = hooks._reflection_cache[TASK.task_id]
    assert record.status == "completed"
    assert record.session_id == SESSION_ID
    assert record.same_session_verified is True
    assert record.trajectory_prefix_verified is True
    assert record.export_prefix_verified is True
    assert record.task_workspace_hash_before == record.task_workspace_hash_after
    assert record.solve_trajectory_path == audit / "trajectory.solve.json"
    assert record.full_session_trajectory_path == audit / "trajectory.full.json"
    assert len(record.solve_trajectory_sha256 or "") == 64
    assert any(kind == "reflection_completed" for kind, _ in events.items)


def test_continuity_accepts_exact_pinned_cli_prompt_rendering() -> None:
    prompt = '# Reflect\n\nFeedback: {"passed": true}\nPath: C:\\work\n'
    cli_rendered = '"' + prompt.replace('"', r'\"') + '"'
    solve_trajectory = _trajectory(
        [("user", "solve prompt"), ("agent", "solve answer")]
    )
    full_trajectory = _trajectory(
        [
            ("user", "solve prompt"),
            ("agent", "solve answer"),
            ("user", cli_rendered),
            ("agent", "reflection answer"),
        ]
    )
    solve_export = _solve_export()
    full_export = {
        "info": {"id": SESSION_ID},
        "messages": [
            *_solve_export()["messages"],
            _export_message("user", cli_rendered),
            _export_message("assistant", "reflection answer"),
        ],
    }

    assert (
        SkillEvolBenchHooks._verify_trajectory_continuity(
            solve_trajectory,
            full_trajectory,
            prompt=prompt,
            task_id=TASK.task_id,
        )
        == SESSION_ID
    )
    assert (
        SkillEvolBenchHooks._verify_export_continuity(
            solve_export,
            full_export,
            prompt=prompt,
            task_id=TASK.task_id,
        )
        == SESSION_ID
    )


@pytest.mark.parametrize(
    "near_miss",
    [
        '"# Reflect\\nFeedback: {\\"passed\\": true}',
        '"# Reflect\nFeedback: {"passed\\": true}\n"',
        'prefix "# Reflect\nFeedback: {\\"passed\\": true}\n"',
        json.dumps('# Reflect\nFeedback: {"passed": true}\n'),
    ],
)
def test_continuity_rejects_near_miss_prompt_rendering(near_miss: str) -> None:
    prompt = '# Reflect\nFeedback: {"passed": true}\n'
    solve = _trajectory([("user", "solve"), ("agent", "answer")])
    full = _trajectory(
        [
            ("user", "solve"),
            ("agent", "answer"),
            ("user", near_miss),
            ("agent", "reflection"),
        ]
    )

    with pytest.raises(UnscoreableTrialError) as error:
        SkillEvolBenchHooks._verify_trajectory_continuity(
            solve,
            full,
            prompt=prompt,
            task_id=TASK.task_id,
        )

    assert error.value.reason == "reflection-trajectory-tail-invalid"


def test_candidate_symlink_is_rejected_without_following_it(tmp_path: Path) -> None:
    hooks, trial, events = _build(tmp_path, candidate_kind="symlink")

    asyncio.run(hooks.on_post_verifier(trial))

    record = hooks._reflection_cache[TASK.task_id]
    assert record.status == "rejected"
    assert record.reason == "candidate_file_not_regular"
    assert record.candidate_path is None
    assert trial.outside_candidate.is_file()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert not (
        tmp_path / "self-reflection-audit" / "self_reflection_patch.json"
    ).exists()
    assert any(kind == "reflection_rejected" for kind, _ in events.items)


def test_secret_candidate_is_rejected_and_raw_file_is_not_retained(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "unit-test-secret")
    hooks, trial, _events = _build(tmp_path, candidate_kind="secret")

    asyncio.run(hooks.on_post_verifier(trial))

    record = hooks._reflection_cache[TASK.task_id]
    assert record.status == "rejected"
    assert record.reason == "candidate_contains_secret:MODEL_API_KEY"
    assert record.candidate_path is None
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert not (
        tmp_path / "self-reflection-audit" / "self_reflection_patch.json"
    ).exists()


@pytest.mark.parametrize(
    ("trial_kwargs", "reason"),
    [
        ({"mutate_task": True}, "reflection-mutated-task-workspace"),
        ({"bad_prefix": True}, "reflection-trajectory-prefix-mismatch"),
    ],
)
def test_reflection_boundary_violations_fail_closed_and_restore_verifier(
    tmp_path: Path, trial_kwargs: dict, reason: str
) -> None:
    hooks, trial, _events = _build(tmp_path, **trial_kwargs)

    with pytest.raises(UnscoreableTrialError) as error:
        asyncio.run(hooks.on_post_verifier(trial))

    assert error.value.reason == reason
    assert not trial.agent_environment.running
    assert (trial.paths.verifier_dir / "reward.txt").is_file()
    assert (
        tmp_path / "self-reflection-audit" / "official-verifier" / "reward.txt"
    ).is_file()
    assert TASK.task_id not in hooks._reflection_cache


def test_verifier_stays_hidden_when_main_cannot_be_proven_stopped(
    tmp_path: Path,
) -> None:
    hooks, trial, _events = _build(tmp_path)
    trial.agent_environment.refuse_stop = True

    with pytest.raises(UnscoreableTrialError) as error:
        asyncio.run(hooks.on_post_verifier(trial))

    assert error.value.reason == "reflection-main-still-running"
    assert trial.agent_environment.running
    assert not any(trial.paths.verifier_dir.iterdir())
    assert (
        tmp_path / "self-reflection-audit" / "official-verifier" / "reward.txt"
    ).is_file()
