from __future__ import annotations

import asyncio
import importlib
import json
import sys
from pathlib import Path
from types import ModuleType, SimpleNamespace
from typing import Any

import pytest


SESSION_ID = "ses_solve_123"


class _FakeInstalledAgent:
    SUPPORTS_RESUME = True
    _resume = False

    def __init__(
        self,
        *,
        logs_dir: Path,
        model_name: str = "openai-compatible/test-model",
        **kwargs: Any,
    ) -> None:
        self.logs_dir = logs_dir
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.model_name = model_name
        self._resume = False
        self._instruction = None
        self._extra_env = kwargs.get("extra_env", {})
        self.logger = SimpleNamespace(debug=lambda *args, **kwargs: None)

    async def exec_as_agent(self, environment, command: str, env=None, **kwargs):
        return await environment.execute(self, command, env or {})

    def _build_register_skills_command(self):
        return None

    def _build_register_config_command(self):
        return None

    def build_cli_flags(self) -> str:
        return ""

    def version(self) -> str:
        return "1.18.3"

    async def resume(self, instruction: str, environment, context) -> None:
        self._resume = True
        try:
            await self.run(instruction, environment, context)
        finally:
            self._resume = False


class _FakeOpenCode(_FakeInstalledAgent):
    pass


class _FakeClaudeCode(_FakeInstalledAgent):
    pass


class _FakeCodex(_FakeInstalledAgent):
    pass


class _FakeGeminiCli(_FakeInstalledAgent):
    pass


class _FakeKimiCli(_FakeInstalledAgent):
    pass


class _FakeNonZeroAgentExitCodeError(RuntimeError):
    pass


def _identity_decorator(function):
    return function


@pytest.fixture
def preinstalled_module(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    module_names = (
        "harbor",
        "harbor.agents",
        "harbor.agents.installed",
        "harbor.agents.installed.base",
        "harbor.agents.installed.claude_code",
        "harbor.agents.installed.codex",
        "harbor.agents.installed.gemini_cli",
        "harbor.agents.installed.kimi_cli",
        "harbor.agents.installed.opencode",
        "harbor.environments",
        "harbor.environments.base",
    )
    modules = {name: ModuleType(name) for name in module_names}
    for name in (
        "harbor",
        "harbor.agents",
        "harbor.agents.installed",
        "harbor.environments",
    ):
        modules[name].__path__ = []  # type: ignore[attr-defined]

    modules[
        "harbor.agents.installed.base"
    ].NonZeroAgentExitCodeError = _FakeNonZeroAgentExitCodeError
    modules["harbor.agents.installed.base"].with_prompt_template = _identity_decorator
    modules["harbor.agents.installed.claude_code"].ClaudeCode = _FakeClaudeCode
    modules["harbor.agents.installed.codex"].Codex = _FakeCodex
    modules["harbor.agents.installed.gemini_cli"].GeminiCli = _FakeGeminiCli
    modules["harbor.agents.installed.kimi_cli"].KimiCli = _FakeKimiCli
    modules["harbor.agents.installed.kimi_cli"]._OUTPUT_FILENAME = "kimi.txt"
    modules["harbor.agents.installed.kimi_cli"]._PROVIDER_CONFIG = {}
    modules["harbor.agents.installed.opencode"].OpenCode = _FakeOpenCode
    modules["harbor.environments.base"].BaseEnvironment = object

    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)
    monkeypatch.delitem(sys.modules, "agents_port.preinstalled", raising=False)
    module = importlib.import_module("agents_port.preinstalled")
    yield module
    sys.modules.pop("agents_port.preinstalled", None)


def _stream(session_id: str, text: str) -> str:
    events = [
        {
            "type": "step_start",
            "timestamp": 1_700_000_000_000,
            "sessionID": session_id,
            "part": {"type": "step-start"},
        },
        {
            "type": "text",
            "timestamp": 1_700_000_000_100,
            "sessionID": session_id,
            "part": {"type": "text", "text": text},
        },
        {
            "type": "step_finish",
            "timestamp": 1_700_000_000_200,
            "sessionID": session_id,
            "part": {
                "type": "step-finish",
                "tokens": {"input": 10, "output": 2, "cache": {}},
            },
        },
    ]
    return "\n".join(json.dumps(event) for event in events) + "\n"


def _message(
    role: str,
    message_id: str,
    parts: list[dict[str, Any]],
    *,
    session_id: str = SESSION_ID,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> dict[str, Any]:
    normalized_parts = []
    for index, part in enumerate(parts):
        normalized_parts.append(
            {
                **part,
                "id": f"part-{message_id}-{index}",
                "messageID": message_id,
                "sessionID": session_id,
            }
        )
    info: dict[str, Any] = {
        "role": role,
        "id": message_id,
        "sessionID": session_id,
        "time": {"created": 1_700_000_000_000 + len(message_id)},
    }
    if role == "assistant":
        info.update(
            {
                "modelID": "test-model",
                "providerID": "openai-compatible",
                "cost": 0.25,
                "tokens": {
                    "input": input_tokens,
                    "output": output_tokens,
                    "reasoning": 3,
                    "cache": {"read": 4, "write": 1},
                },
            }
        )
    return {"info": info, "parts": normalized_parts}


def _export(*, include_reflection: bool, session_id: str = SESSION_ID):
    solve_user = _message(
        "user",
        "solve-user",
        [{"type": "text", "text": "solve prompt"}],
        session_id=session_id,
    )
    solve_assistant = _message(
        "assistant",
        "solve-assistant",
        [
            {"type": "reasoning", "text": "solve reasoning"},
            {"type": "text", "text": "solve answer"},
            {
                "type": "tool",
                "tool": "read",
                "callID": "call-solve",
                "state": {
                    "input": {"filePath": "/workspace/input.txt"},
                    "output": "input contents",
                },
            },
        ],
        session_id=session_id,
        input_tokens=10,
        output_tokens=2,
    )
    messages = [solve_user, solve_assistant]
    total_input = 10
    total_output = 2
    if include_reflection:
        messages.extend(
            [
                _message(
                    "user",
                    "reflection-user",
                    [{"type": "text", "text": "verifier passed; reflect"}],
                    session_id=session_id,
                ),
                _message(
                    "assistant",
                    "reflection-assistant",
                    [
                        {"type": "reasoning", "text": "reflection reasoning"},
                        {"type": "text", "text": "reflection answer"},
                        {
                            "type": "tool",
                            "tool": "write",
                            "callID": "call-reflect",
                            "state": {
                                "input": {
                                    "filePath": "/logs/agent/reflection.json",
                                    "content": "{}",
                                },
                                "output": "Wrote file successfully.",
                            },
                        },
                    ],
                    session_id=session_id,
                    input_tokens=20,
                    output_tokens=5,
                ),
            ]
        )
        total_input += 20
        total_output += 5
    return {
        "info": {
            "id": session_id,
            "version": "1.18.3",
            "cost": 0.25 * (2 if include_reflection else 1),
            "tokens": {
                "input": total_input,
                "output": total_output,
                "reasoning": 3 * (2 if include_reflection else 1),
                "cache": {
                    "read": 4 * (2 if include_reflection else 1),
                    "write": 1 * (2 if include_reflection else 1),
                },
            },
        },
        "messages": messages,
    }


class _ScriptedEnvironment:
    def __init__(
        self,
        *,
        solve_session_id: str = SESSION_ID,
        reflection_session_id: str = SESSION_ID,
        solve_stream_suffix: str = "",
        truncate_phase_stdout: bool = False,
    ) -> None:
        self.solve_session_id = solve_session_id
        self.reflection_session_id = reflection_session_id
        self.solve_stream_suffix = solve_stream_suffix
        self.truncate_phase_stdout = truncate_phase_stdout
        self.commands: list[str] = []
        self.exports = 0

    async def execute(self, agent, command: str, env: dict[str, str]):
        self.commands.append(command)
        if "opencode export " in command:
            self.exports += 1
            payload = _export(
                include_reflection=self.exports == 2,
                session_id=self.solve_session_id,
            )
            (agent.logs_dir / "opencode.session.json").write_text(json.dumps(payload))
            return SimpleNamespace(stdout="", stderr="", return_code=0)

        if "opencode.reflection.jsonl" in command:
            output = _stream(self.reflection_session_id, "reflection answer")
            (agent.logs_dir / "opencode.reflection.jsonl").write_text(output)
        elif "opencode.solve.jsonl" in command:
            output = (
                _stream(self.solve_session_id, "solve answer")
                + self.solve_stream_suffix
            )
            (agent.logs_dir / "opencode.solve.jsonl").write_text(output)
        else:
            raise AssertionError(f"unexpected command: {command}")
        stdout = output
        if self.truncate_phase_stdout:
            stdout = output.splitlines(keepends=True)[0]
        return SimpleNamespace(stdout=stdout, stderr="", return_code=0)


def _context() -> SimpleNamespace:
    return SimpleNamespace(
        cost_usd=None,
        n_input_tokens=0,
        n_output_tokens=0,
        n_cache_tokens=0,
    )


def test_run_and_resume_use_one_explicit_session_and_keep_both_streams(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    environment = _ScriptedEnvironment()

    asyncio.run(agent.run("solve prompt", environment, _context()))
    asyncio.run(agent.resume("verifier passed; reflect", environment, _context()))

    assert agent.opencode_session_id == SESSION_ID
    assert "solve answer" in (tmp_path / "opencode.solve.jsonl").read_text()
    assert "reflection answer" in (tmp_path / "opencode.reflection.jsonl").read_text()
    solve_trajectory = json.loads((tmp_path / "trajectory.solve.json").read_text())
    assert [step["message"] for step in solve_trajectory["steps"]] == [
        "solve prompt",
        "solve answer",
    ]

    solve_command, first_export, reflection_command, second_export = (
        environment.commands
    )
    assert "--continue" not in "\n".join(environment.commands)
    assert "--session" not in solve_command
    assert f"--session {SESSION_ID}" in reflection_command
    assert "opencode.solve.jsonl" in solve_command
    assert "opencode.reflection.jsonl" in reflection_command
    assert f"opencode export {SESSION_ID}" in first_export
    assert f"opencode export {SESSION_ID}" in second_export


def test_phase_validation_prefers_complete_tee_when_stdout_is_truncated(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    error_event = json.dumps(
        {
            "type": "error",
            "sessionID": SESSION_ID,
            "error": {
                "name": "ProviderError",
                "data": {"message": "error visible only in complete tee"},
            },
        }
    ) + "\n"
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    environment = _ScriptedEnvironment(
        solve_stream_suffix=error_event,
        truncate_phase_stdout=True,
    )

    with pytest.raises(
        preinstalled_module.NonZeroAgentExitCodeError,
        match="error visible only in complete tee",
    ):
        asyncio.run(agent.run("solve prompt", environment, _context()))

    assert environment.exports == 1
    assert error_event.strip() in (tmp_path / "opencode.solve.jsonl").read_text()


def test_export_is_canonical_complete_trajectory_and_populates_context(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    environment = _ScriptedEnvironment()
    context = _context()

    asyncio.run(agent.run("solve prompt", environment, context))
    asyncio.run(agent.resume("verifier passed; reflect", environment, context))
    agent.populate_context_post_run(context)

    raw_export = json.loads((tmp_path / "opencode.session.json").read_text())
    solve_trajectory = json.loads((tmp_path / "trajectory.solve.json").read_text())
    trajectory = json.loads((tmp_path / "trajectory.json").read_text())
    assert raw_export == _export(include_reflection=True)
    assert [step["source"] for step in solve_trajectory["steps"]] == [
        "user",
        "agent",
    ]
    assert trajectory["session_id"] == SESSION_ID
    assert [step["source"] for step in trajectory["steps"]] == [
        "user",
        "agent",
        "user",
        "agent",
    ]
    assert [step["message"] for step in trajectory["steps"]] == [
        "solve prompt",
        "solve answer",
        "verifier passed; reflect",
        "reflection answer",
    ]
    solve_step = trajectory["steps"][1]
    reflection_step = trajectory["steps"][3]
    assert solve_step["reasoning_content"] == "solve reasoning"
    assert solve_step["tool_calls"][0] == {
        "tool_call_id": "call-solve",
        "function_name": "read",
        "arguments": {"filePath": "/workspace/input.txt"},
    }
    assert solve_step["observation"]["results"][0]["content"] == ("input contents")
    assert reflection_step["reasoning_content"] == "reflection reasoning"
    assert reflection_step["tool_calls"][0]["arguments"]["content"] == "{}"
    assert reflection_step["observation"]["results"][0]["content"] == (
        "Wrote file successfully."
    )
    assert solve_step["metrics"] == {
        "prompt_tokens": 14,
        "completion_tokens": 2,
        "cached_tokens": 4,
        "cost_usd": 0.25,
        "extra": {"reasoning_tokens": 3, "cache_write_tokens": 1},
    }
    assert trajectory["final_metrics"] == {
        "total_prompt_tokens": 38,
        "total_completion_tokens": 7,
        "total_steps": 4,
        "total_cached_tokens": 8,
        "total_cost_usd": 0.5,
    }
    assert context.cost_usd == 0.5
    assert context.n_input_tokens == 38
    assert context.n_output_tokens == 7
    assert context.n_cache_tokens == 8


def test_export_normalizes_pinned_cli_user_prompt_rendering(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    agent._opencode_session_id = SESSION_ID
    prompt = '# Reflect\n\nFeedback: {"passed": true}\nPath: C:\\work\n'
    cli_rendered = '"' + prompt.replace('"', r'\"') + '"'
    export = _export(include_reflection=False)
    export["messages"][0]["parts"][0]["text"] = cli_rendered

    trajectory = agent._convert_export_to_trajectory(export)

    assert trajectory["steps"][0]["message"] == prompt


def test_export_does_not_guess_at_near_miss_cli_rendering(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    agent._opencode_session_id = SESSION_ID
    near_miss = '"quoted but has an unescaped " interior"'
    export = _export(include_reflection=False)
    export["messages"][0]["parts"][0]["text"] = near_miss

    trajectory = agent._convert_export_to_trajectory(export)

    assert trajectory["steps"][0]["message"] == near_miss


def test_resume_fails_closed_when_stream_switches_session(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    environment = _ScriptedEnvironment(reflection_session_id="ses_wrong")
    asyncio.run(agent.run("solve prompt", environment, _context()))

    with pytest.raises(RuntimeError, match="escaped the solve session"):
        asyncio.run(agent.resume("verifier passed; reflect", environment, _context()))

    assert environment.exports == 1
    assert "--continue" not in "\n".join(environment.commands)
    assert f"--session {SESSION_ID}" in environment.commands[-1]


def test_session_id_is_shell_quoted_in_resume_and_export(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    session_id = "ses with spaces;still-one-argument"
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    environment = _ScriptedEnvironment(
        solve_session_id=session_id,
        reflection_session_id=session_id,
    )

    asyncio.run(agent.run("solve prompt", environment, _context()))
    asyncio.run(agent.resume("reflect", environment, _context()))

    commands = "\n".join(environment.commands)
    assert "--session 'ses with spaces;still-one-argument'" in commands
    assert "opencode export 'ses with spaces;still-one-argument'" in commands


def test_export_rejects_cross_session_message(
    tmp_path: Path,
    preinstalled_module,
) -> None:
    agent = preinstalled_module.OpenCodePreinstalled(logs_dir=tmp_path)
    agent._opencode_session_id = SESSION_ID
    export = _export(include_reflection=True)
    export["messages"][-1]["info"]["sessionID"] = "ses_wrong"

    with pytest.raises(RuntimeError, match="message from another session"):
        agent._convert_export_to_trajectory(export)
