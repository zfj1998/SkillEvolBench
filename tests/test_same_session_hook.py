from __future__ import annotations

import asyncio
import copy
import json
import shutil
from contextlib import contextmanager
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.components.verifier_adapter import UnscoreableTrialError
from skillevolbench.harbor_ext import hooks as hooks_module
from skillevolbench.harbor_ext.hooks import SkillEvolBenchHooks
from skillevolbench.opencode_continuity import (
    OPENCODE_AUTO_COMPACTION_KIND,
    OPENCODE_COMPACTION_CONTINUE_KIND,
    OPENCODE_COMPACTION_SUMMARY_KIND,
    OPENCODE_EVENT_KEY,
    OPENCODE_POST_COMPACTION_ASSISTANT_KIND,
    opencode_synthetic_continue,
)
from skillevolbench.schemas import TrialOutcome


SESSION_ID = "ses-1"


class _FakeAgentTimeoutError(asyncio.TimeoutError):
    pass


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


def _trajectory_with_tail(solve: dict, tail: list[dict]) -> dict:
    full = copy.deepcopy(solve)
    full["steps"].extend(copy.deepcopy(tail))
    for index, step in enumerate(full["steps"], start=1):
        step["step_id"] = index
    return full


def _trajectory_compaction_sequence(
    index: int, *, overflow: bool = False
) -> list[dict]:
    compaction_id = f"compaction-{index}"
    summary_id = f"summary-{index}"
    continue_id = f"continue-{index}"
    return [
        {
            "source": "user",
            "message": "",
            OPENCODE_EVENT_KEY: {
                "kind": OPENCODE_AUTO_COMPACTION_KIND,
                "auto": True,
                "overflow": overflow,
                "exclusive": True,
                "message_id": compaction_id,
                "part_message_id": compaction_id,
            },
        },
        {
            "source": "agent",
            "message": "bounded summary",
            OPENCODE_EVENT_KEY: {
                "kind": OPENCODE_COMPACTION_SUMMARY_KIND,
                "summary": True,
                "mode": "compaction",
                "agent": "compaction",
                "message_id": summary_id,
                "parent_id": compaction_id,
            },
        },
        {
            "source": "user",
            "message": opencode_synthetic_continue(overflow=overflow),
            OPENCODE_EVENT_KEY: {
                "kind": OPENCODE_COMPACTION_CONTINUE_KIND,
                "synthetic": True,
                "metadata": {"compaction_continue": True},
                "exclusive": True,
                "message_id": continue_id,
                "part_message_id": continue_id,
            },
        },
        {
            "source": "agent",
            "message": "continued reflection",
            OPENCODE_EVENT_KEY: {
                "kind": OPENCODE_POST_COMPACTION_ASSISTANT_KIND,
                "ordinary": True,
                "continue_message_id": continue_id,
                "parent_id": continue_id,
            },
        },
    ]


def _export_compaction_sequence(index: int, *, overflow: bool = False) -> list[dict]:
    compaction_id = f"compaction-{index}"
    summary_id = f"summary-{index}"
    continue_id = f"continue-{index}"
    return_id = f"return-{index}"
    return [
        {
            "info": {
                "id": compaction_id,
                "role": "user",
                "sessionID": SESSION_ID,
            },
            "parts": [
                {
                    "type": "compaction",
                    "auto": True,
                    "overflow": overflow,
                    "messageID": compaction_id,
                    "sessionID": SESSION_ID,
                }
            ],
        },
        {
            "info": {
                "id": summary_id,
                "role": "assistant",
                "sessionID": SESSION_ID,
                "parentID": compaction_id,
                "mode": "compaction",
                "agent": "compaction",
                "summary": True,
            },
            "parts": [
                {
                    "type": "text",
                    "text": "bounded summary",
                    "messageID": summary_id,
                    "sessionID": SESSION_ID,
                }
            ],
        },
        {
            "info": {
                "id": continue_id,
                "role": "user",
                "sessionID": SESSION_ID,
            },
            "parts": [
                {
                    "type": "text",
                    "text": opencode_synthetic_continue(overflow=overflow),
                    "synthetic": True,
                    "metadata": {"compaction_continue": True},
                    "messageID": continue_id,
                    "sessionID": SESSION_ID,
                }
            ],
        },
        {
            "info": {
                "id": return_id,
                "role": "assistant",
                "sessionID": SESSION_ID,
                "parentID": continue_id,
            },
            "parts": [
                {
                    "type": "text",
                    "text": "continued reflection",
                    "messageID": return_id,
                    "sessionID": SESSION_ID,
                }
            ],
        },
    ]


def _compacted_continuity_payloads(
    overflows: tuple[bool, ...] = (False,),
) -> tuple[dict, dict, dict, dict]:
    prompt = "reflect exactly"
    solve_trajectory = _trajectory(
        [("user", "solve prompt"), ("agent", "solve answer")]
    )
    trajectory_tail = [
        {"source": "user", "message": prompt},
        {"source": "agent", "message": "reflection before compaction"},
    ]
    export_tail = [
        _export_message("user", prompt),
        _export_message("assistant", "reflection before compaction"),
    ]
    for index, overflow in enumerate(overflows):
        trajectory_tail.extend(
            _trajectory_compaction_sequence(index, overflow=overflow)
        )
        export_tail.extend(_export_compaction_sequence(index, overflow=overflow))
    full_trajectory = _trajectory_with_tail(solve_trajectory, trajectory_tail)
    solve_export = _solve_export()
    full_export = {
        "info": {"id": SESSION_ID},
        "messages": [*copy.deepcopy(solve_export["messages"]), *export_tail],
    }
    return solve_trajectory, full_trajectory, solve_export, full_export


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
        self.restart_calls = 0
        self.default_users: list[object] = []
        self.exec_envs: list[dict[str, str]] = []

    async def empty_dirs(self, paths, chmod=False) -> None:
        self.empty_calls.append((list(paths), chmod))

    async def restart_main_service(self) -> None:
        self.restart_calls += 1
        self.running = True

    @contextmanager
    def with_default_user(self, user):
        self.default_users.append(user)
        yield

    @contextmanager
    def scoped_exec_env(self, env):
        self.exec_envs.append(dict(env))
        yield

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
        self.extra_env = {"OPENAI_API_KEY": "resolved-in-memory"}
        self.recovery_calls = 0
        self.recovery_timeout_sec: int | None = None

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

    async def recover_timed_out_resume(self, environment, *, timeout_sec: int) -> str:
        self.recovery_calls += 1
        self.recovery_timeout_sec = timeout_sec
        assert environment.running
        self.trial.verifier_was_hidden_during_recovery = not any(
            self.trial.paths.verifier_dir.iterdir()
        )
        if self.trial.recovery_failure:
            raise RuntimeError("export failed")
        instruction = self.trial.reflection_instruction
        assert instruction is not None
        solve_messages = list(_solve_export()["messages"])
        if self.trial.bad_prefix:
            solve_messages[1] = _export_message("assistant", "tampered solve")
        solve_messages.append(_export_message("user", instruction))
        if not self.trial.missing_assistant_tail:
            solve_messages.append(
                _export_message("assistant", "encoded a reusable lesson")
            )
        export = {"info": {"id": SESSION_ID}, "messages": solve_messages}
        (self.trial.paths.agent_dir / "opencode.session.json").write_text(
            json.dumps(export)
        )
        steps = [
            (
                "user" if message["info"]["role"] == "user" else "agent",
                message["parts"][0]["text"],
            )
            for message in solve_messages
        ]
        (self.trial.paths.agent_dir / "trajectory.json").write_text(
            json.dumps(_trajectory(steps))
        )
        return SESSION_ID


class _Trial:
    def __init__(
        self,
        root: Path,
        *,
        mutate_task: bool = False,
        bad_prefix: bool = False,
        candidate_kind: str = "valid",
        phase_error: str | None = None,
        missing_reflection_stream: bool = False,
        missing_assistant_tail: bool = False,
        recovery_failure: bool = False,
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
        (self.paths.verifier_dir / "hidden-detail.json").write_text('{"secret": true}')
        self.task_workspace = root / "container-task"
        self.task_workspace.mkdir()
        (self.task_workspace / "answer.txt").write_text("solve state\n")
        task_snapshot = self.paths.artifacts_dir / "root" / "task"
        task_snapshot.mkdir(parents=True)
        (task_snapshot / "answer.txt").write_text("solve state\n")
        (self.paths.agent_dir / "trajectory.json").write_text(
            json.dumps(
                _trajectory([("user", "solve prompt"), ("agent", "solve answer")])
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
        self.primary_agent_result = SimpleNamespace(source="solve")
        self.result = SimpleNamespace(
            agent_result=self.primary_agent_result,
            exception_info=None,
        )
        self.agent_environment = _Environment(self.task_workspace)
        self.agent = _Agent(self)
        self.agent_env_paths = SimpleNamespace(tests_dir="/tests")
        self._agent_timeout_sec = 60
        self._is_agent_environment_stopped = False
        self._sevb_agent_main_stopped = True
        self._sevb_agent_container_identity = "container-1"
        self.verifier_was_hidden_during_resume = False
        self.verifier_was_hidden_during_recovery = False
        self.verifier_was_hidden_at_cleanup = False
        self.mutate_task = mutate_task
        self.bad_prefix = bad_prefix
        self.candidate_kind = candidate_kind
        self.phase_error = phase_error
        self.missing_reflection_stream = missing_reflection_stream
        self.missing_assistant_tail = missing_assistant_tail
        self.recovery_failure = recovery_failure
        self.reflection_instruction: str | None = None
        self.outside_candidate = root / "outside-candidate.json"

    async def _run_agent_phase(self, *, target, instruction, resume, **_kwargs):
        assert resume is True
        assert self.agent_environment.running
        assert "official verifier" in instruction
        self.verifier_was_hidden_during_resume = not any(
            self.paths.verifier_dir.iterdir()
        )
        self.reflection_instruction = instruction
        current_export = json.loads(
            (self.paths.agent_dir / "opencode.session.json").read_text()
        )
        solve_messages = list(current_export["messages"])
        if self.bad_prefix:
            solve_messages[1] = _export_message("assistant", "tampered solve")
        solve_messages.extend(
            [
                _export_message("user", instruction),
                _export_message("assistant", "encoded a reusable lesson"),
            ]
        )
        if self.phase_error is None:
            (self.paths.agent_dir / "opencode.session.json").write_text(
                json.dumps({"info": {"id": SESSION_ID}, "messages": solve_messages})
            )
        if not self.missing_reflection_stream:
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

        if self.phase_error == "agent_timeout":
            raise _FakeAgentTimeoutError("reflection timed out")
        if self.phase_error == "generic_timeout":
            raise asyncio.TimeoutError("not Harbor AgentTimeoutError")
        if self.phase_error == "runtime_error":
            raise RuntimeError("reflection failed")

        target.agent_result = SimpleNamespace(
            cost_usd=None,
            n_input_tokens=0,
            n_output_tokens=0,
            n_cache_tokens=0,
        )

    async def _stop_agent_environment(self) -> None:
        self.verifier_was_hidden_at_cleanup = not any(self.paths.verifier_dir.iterdir())
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


def test_failed_learning_attempt_repairs_same_session_before_reverify(
    tmp_path: Path,
) -> None:
    hooks, trial, events = _build(tmp_path, mutate_task=True)
    hooks.runtime.baseline.learning_max_attempts = 3

    should_reverify = asyncio.run(hooks.on_post_verifier_repair(trial, 1))

    assert should_reverify is True
    assert trial.agent.opencode_session_id == SESSION_ID
    assert trial.agent_environment.restart_calls == 1
    assert trial.agent_environment.stop_calls == 1
    assert trial.verifier_was_hidden_during_resume is True
    assert not any(trial.paths.verifier_dir.iterdir())
    assert (
        trial.paths.artifacts_dir / "root" / "task" / "answer.txt"
    ).read_text() == "reflection mutation\n"

    attempt = tmp_path / "same-session-attempts" / "attempt-01"
    assert (attempt / "official-verifier" / "reward.txt").read_text() == "0.0\n"
    assert (attempt / "repair_prompt.md").is_file()
    assert (attempt / "trajectory.before-repair.json").is_file()
    assert (attempt / "trajectory.after-repair.json").is_file()
    assert (attempt / "opencode.repair.jsonl").is_file()
    result = json.loads((attempt / "repair_result.json").read_text())
    assert result["session_id"] == SESSION_ID
    assert result["same_session_verified"] is True
    assert result["task_hash_before"] != result["task_hash_after"]
    assert any(kind == "same_session_repair_completed" for kind, _ in events.items)


def test_two_repairs_extend_one_session_monotonically(tmp_path: Path) -> None:
    hooks, trial, _events = _build(tmp_path, mutate_task=True)
    hooks.runtime.baseline.learning_max_attempts = 3

    assert asyncio.run(hooks.on_post_verifier_repair(trial, 1)) is True
    (trial.paths.verifier_dir / "reward.txt").write_text("0.0\n")
    (trial.paths.verifier_dir / "hidden-detail.json").write_text('{"secret": true}')
    assert asyncio.run(hooks.on_post_verifier_repair(trial, 2)) is True

    records = trial._sevb_repair_records
    assert len(records) == 2
    assert {record["session_id"] for record in records} == {SESSION_ID}
    assert all(record["same_session_verified"] is True for record in records)
    first_after = json.loads(
        (
            tmp_path
            / "same-session-attempts"
            / "attempt-01"
            / "trajectory.after-repair.json"
        ).read_text()
    )
    second_before = json.loads(
        (
            tmp_path
            / "same-session-attempts"
            / "attempt-02"
            / "trajectory.before-repair.json"
        ).read_text()
    )
    assert first_after == second_before


def test_continuity_accepts_exact_pinned_cli_prompt_rendering() -> None:
    prompt = '# Reflect\n\nFeedback: {"passed": true}\nPath: C:\\work\n'
    cli_rendered = '"' + prompt.replace('"', r"\"") + '"'
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


@pytest.mark.parametrize("overflows", [(False,), (True,), (False, True)])
def test_continuity_accepts_strict_auto_compaction_sequences(
    overflows: tuple[bool, ...],
) -> None:
    solve_trajectory, full_trajectory, solve_export, full_export = (
        _compacted_continuity_payloads(overflows)
    )

    assert (
        SkillEvolBenchHooks._verify_trajectory_continuity(
            solve_trajectory,
            full_trajectory,
            prompt="reflect exactly",
            task_id=TASK.task_id,
        )
        == SESSION_ID
    )
    assert (
        SkillEvolBenchHooks._verify_export_continuity(
            solve_export,
            full_export,
            prompt="reflect exactly",
            task_id=TASK.task_id,
        )
        == SESSION_ID
    )


@pytest.mark.parametrize(
    "near_miss",
    [
        "auto_false",
        "overflow_not_bool",
        "nonexclusive_compaction",
        "missing_summary",
        "misordered_summary",
        "summary_false",
        "summary_parent_mismatch",
        "wrong_continue",
        "continue_metadata_false",
        "missing_return_assistant",
        "return_parent_mismatch",
        "arbitrary_user",
    ],
)
def test_trajectory_compaction_near_misses_fail_closed(near_miss: str) -> None:
    solve, full, _solve_export_payload, _full_export_payload = (
        _compacted_continuity_payloads()
    )
    tail = full["steps"][len(solve["steps"]) :]
    compaction, summary, synthetic_continue, returned = tail[2:6]

    if near_miss == "auto_false":
        compaction[OPENCODE_EVENT_KEY]["auto"] = False
    elif near_miss == "overflow_not_bool":
        compaction[OPENCODE_EVENT_KEY]["overflow"] = "false"
    elif near_miss == "nonexclusive_compaction":
        compaction[OPENCODE_EVENT_KEY]["exclusive"] = False
    elif near_miss == "missing_summary":
        tail.pop(3)
    elif near_miss == "misordered_summary":
        tail[3], tail[4] = tail[4], tail[3]
    elif near_miss == "summary_false":
        summary[OPENCODE_EVENT_KEY]["summary"] = False
    elif near_miss == "summary_parent_mismatch":
        summary[OPENCODE_EVENT_KEY]["parent_id"] = "wrong-parent"
    elif near_miss == "wrong_continue":
        synthetic_continue["message"] += " altered"
    elif near_miss == "continue_metadata_false":
        synthetic_continue[OPENCODE_EVENT_KEY]["metadata"] = {
            "compaction_continue": False
        }
    elif near_miss == "missing_return_assistant":
        tail.pop(5)
    elif near_miss == "return_parent_mismatch":
        returned[OPENCODE_EVENT_KEY]["parent_id"] = "wrong-parent"
    elif near_miss == "arbitrary_user":
        tail.insert(2, {"source": "user", "message": "arbitrary user turn"})
    else:  # pragma: no cover - guarded by the parameter list
        raise AssertionError(near_miss)
    full["steps"] = [*solve["steps"], *tail]

    with pytest.raises(UnscoreableTrialError) as error:
        SkillEvolBenchHooks._verify_trajectory_continuity(
            solve,
            full,
            prompt="reflect exactly",
            task_id=TASK.task_id,
        )

    assert error.value.reason == "reflection-trajectory-tail-invalid"


@pytest.mark.parametrize(
    "near_miss",
    [
        "auto_false",
        "overflow_not_bool",
        "extra_compaction_part",
        "missing_summary",
        "misordered_summary",
        "summary_false",
        "summary_mode_wrong",
        "summary_agent_wrong",
        "summary_parent_mismatch",
        "wrong_continue",
        "continue_synthetic_false",
        "continue_metadata_false",
        "continue_message_link_mismatch",
        "missing_return_assistant",
        "return_parent_mismatch",
        "arbitrary_user",
    ],
)
def test_export_compaction_near_misses_fail_closed(near_miss: str) -> None:
    _solve_trajectory, _full_trajectory, solve, full = _compacted_continuity_payloads()
    tail = full["messages"][len(solve["messages"]) :]
    compaction, summary, synthetic_continue, returned = tail[2:6]
    compaction_part = compaction["parts"][0]
    continue_part = synthetic_continue["parts"][0]

    if near_miss == "auto_false":
        compaction_part["auto"] = False
    elif near_miss == "overflow_not_bool":
        compaction_part["overflow"] = "false"
    elif near_miss == "extra_compaction_part":
        compaction["parts"].append(
            {"type": "text", "text": "extra", "sessionID": SESSION_ID}
        )
    elif near_miss == "missing_summary":
        tail.pop(3)
    elif near_miss == "misordered_summary":
        tail[3], tail[4] = tail[4], tail[3]
    elif near_miss == "summary_false":
        summary["info"]["summary"] = False
    elif near_miss == "summary_mode_wrong":
        summary["info"]["mode"] = "build"
    elif near_miss == "summary_agent_wrong":
        summary["info"]["agent"] = "build"
    elif near_miss == "summary_parent_mismatch":
        summary["info"]["parentID"] = "wrong-parent"
    elif near_miss == "wrong_continue":
        continue_part["text"] += " altered"
    elif near_miss == "continue_synthetic_false":
        continue_part["synthetic"] = False
    elif near_miss == "continue_metadata_false":
        continue_part["metadata"] = {"compaction_continue": False}
    elif near_miss == "continue_message_link_mismatch":
        continue_part["messageID"] = "wrong-message"
    elif near_miss == "missing_return_assistant":
        tail.pop(5)
    elif near_miss == "return_parent_mismatch":
        returned["info"]["parentID"] = "wrong-parent"
    elif near_miss == "arbitrary_user":
        tail.insert(2, _export_message("user", "arbitrary user turn"))
    else:  # pragma: no cover - guarded by the parameter list
        raise AssertionError(near_miss)
    full["messages"] = [*solve["messages"], *tail]

    with pytest.raises(UnscoreableTrialError) as error:
        SkillEvolBenchHooks._verify_export_continuity(
            solve,
            full,
            prompt="reflect exactly",
            task_id=TASK.task_id,
        )

    assert error.value.reason == "reflection-export-tail-invalid"


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


def test_agent_timeout_with_complete_evidence_is_terminal_rejected(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        hooks_module,
        "_is_agent_timeout_error",
        lambda exc: isinstance(exc, _FakeAgentTimeoutError),
    )
    hooks, trial, events = _build(tmp_path, phase_error="agent_timeout")

    asyncio.run(hooks.on_post_verifier(trial))

    record = hooks._reflection_cache[TASK.task_id]
    assert record.status == "rejected"
    assert record.reason == "reflection_agent_timeout"
    assert record.patch is None
    assert record.same_session_verified is True
    assert record.trajectory_prefix_verified is True
    assert record.export_prefix_verified is True
    assert record.task_workspace_hash_before == record.task_workspace_hash_after
    assert trial.result.agent_result is trial.primary_agent_result
    assert trial.result.exception_info is None
    assert trial.agent.recovery_calls == 1
    assert trial.agent.recovery_timeout_sec == 60
    assert trial.agent_environment.restart_calls == 2
    assert trial.agent_environment.stop_calls == 2
    assert trial.agent_environment.default_users == [None]
    assert trial.agent_environment.exec_envs == [trial.agent.extra_env]
    assert trial.verifier_was_hidden_during_resume is True
    assert trial.verifier_was_hidden_during_recovery is True
    assert trial.verifier_was_hidden_at_cleanup is True
    assert not trial.agent_environment.running
    assert (trial.paths.verifier_dir / "reward.txt").is_file()
    audit = tmp_path / "self-reflection-audit"
    assert (audit / "opencode.reflection.jsonl").is_file()
    assert (audit / "trajectory.full.json").is_file()
    assert (audit / "opencode.session.full.json").is_file()
    assert (audit / "self_reflection_result.json").is_file()
    assert not (audit / "self_reflection_patch.json").exists()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert any(kind == "reflection_rejected" for kind, _ in events.items)


def test_agent_timeout_missing_stream_remains_unscoreable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        hooks_module,
        "_is_agent_timeout_error",
        lambda exc: isinstance(exc, _FakeAgentTimeoutError),
    )
    hooks, trial, _events = _build(
        tmp_path,
        phase_error="agent_timeout",
        missing_reflection_stream=True,
    )

    with pytest.raises(UnscoreableTrialError) as error:
        asyncio.run(hooks.on_post_verifier(trial))

    assert error.value.reason == "reflection-missing-reflection-stream"
    assert trial.agent.recovery_calls == 0
    assert not trial.agent_environment.running
    assert (trial.paths.verifier_dir / "reward.txt").is_file()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert TASK.task_id not in hooks._reflection_cache


@pytest.mark.parametrize(
    ("trial_kwargs", "reason"),
    [
        (
            {"recovery_failure": True},
            "reflection-timeout-recovery-failed",
        ),
        (
            {"missing_assistant_tail": True},
            "reflection-trajectory-tail-invalid",
        ),
    ],
)
def test_agent_timeout_recovery_failures_remain_unscoreable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    trial_kwargs: dict,
    reason: str,
) -> None:
    monkeypatch.setattr(
        hooks_module,
        "_is_agent_timeout_error",
        lambda exc: isinstance(exc, _FakeAgentTimeoutError),
    )
    hooks, trial, _events = _build(
        tmp_path,
        phase_error="agent_timeout",
        **trial_kwargs,
    )

    with pytest.raises(UnscoreableTrialError) as error:
        asyncio.run(hooks.on_post_verifier(trial))

    assert error.value.reason == reason
    assert trial.agent.recovery_calls == 1
    assert not trial.agent_environment.running
    assert (trial.paths.verifier_dir / "reward.txt").is_file()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert TASK.task_id not in hooks._reflection_cache


def test_generic_timeout_is_not_reclassified_as_reflection_outcome(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        hooks_module,
        "_is_agent_timeout_error",
        lambda exc: isinstance(exc, _FakeAgentTimeoutError),
    )
    hooks, trial, _events = _build(tmp_path, phase_error="generic_timeout")

    with pytest.raises(asyncio.TimeoutError, match="not Harbor"):
        asyncio.run(hooks.on_post_verifier(trial))

    assert trial.agent.recovery_calls == 0
    assert (trial.paths.verifier_dir / "reward.txt").is_file()
    assert not (trial.paths.agent_dir / "self_reflection_patch.json").exists()
    assert TASK.task_id not in hooks._reflection_cache


def test_solve_timeout_remains_unscoreable_before_reflection(
    tmp_path: Path,
) -> None:
    hooks, trial, _events = _build(tmp_path)

    def _raise_solve_timeout(_result):
        raise UnscoreableTrialError(
            "agent-or-runtime-exception",
            task_id=TASK.task_id,
            exception_type="AgentTimeoutError",
        )

    hooks.runtime.verifier_adapter.parse = _raise_solve_timeout

    with pytest.raises(UnscoreableTrialError) as error:
        asyncio.run(hooks.on_post_verifier(trial))

    assert error.value.reason == "agent-or-runtime-exception"
    assert error.value.exception_type == "AgentTimeoutError"
    assert trial.agent_environment.restart_calls == 0
    assert trial.agent.recovery_calls == 0
    assert TASK.task_id not in hooks._reflection_cache
