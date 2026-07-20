import json
import os
import shlex
from datetime import datetime, timezone
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.gemini_cli import GeminiCli
from harbor.agents.installed.kimi_cli import KimiCli, _OUTPUT_FILENAME, _PROVIDER_CONFIG
from harbor.agents.installed.opencode import OpenCode
from harbor.agents.installed.base import NonZeroAgentExitCodeError, with_prompt_template
from harbor.environments.base import BaseEnvironment


def _toml_value(value: Any) -> str:
    if isinstance(value, str):
        return json.dumps(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, dict):
        items = ", ".join(
            f"{json.dumps(str(key))} = {_toml_value(item)}"
            for key, item in value.items()
        )
        return f"{{ {items} }}"
    return str(value)


def _codex_config_flag(key: str, value: Any) -> str:
    return f"-c {shlex.quote(f'{key}={_toml_value(value)}')}"


class _PreinstalledMixin:
    _preinstalled_check_command: str

    async def install(self, environment: BaseEnvironment) -> None:
        try:
            await self.exec_as_agent(
                environment,
                command=self._preinstalled_check_command,
            )
            return
        except Exception:
            await super().install(environment)


class ClaudeCodePreinstalled(_PreinstalledMixin, ClaudeCode):
    _preinstalled_check_command = (
        'export PATH="$HOME/.local/bin:$PATH"; command -v claude && claude --version'
    )
    _passthrough_env = (
        "ANTHROPIC_API_KEY",
        "ANTHROPIC_AUTH_TOKEN",
        "ANTHROPIC_BASE_URL",
        "ANTHROPIC_BEDROCK_BASE_URL",
        "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
        "ANTHROPIC_BEDROCK_SERVICE_TIER",
        "ANTHROPIC_AWS_API_KEY",
        "ANTHROPIC_CUSTOM_HEADERS",
        "ANTHROPIC_DEFAULT_HAIKU_MODEL",
        "ANTHROPIC_DEFAULT_OPUS_MODEL",
        "ANTHROPIC_DEFAULT_SONNET_MODEL",
        "ANTHROPIC_MODEL",
        "ANTHROPIC_SMALL_FAST_MODEL_AWS_REGION",
        "AWS_ACCESS_KEY_ID",
        "AWS_BEARER_TOKEN_BEDROCK",
        "AWS_DEFAULT_PROFILE",
        "AWS_DEFAULT_REGION",
        "AWS_PROFILE",
        "AWS_REGION",
        "AWS_SECRET_ACCESS_KEY",
        "AWS_SESSION_TOKEN",
        "CLAUDE_CODE_USE_ANTHROPIC_AWS",
        "CLAUDE_CODE_USE_BEDROCK",
        "CLAUDE_CODE_USE_MANTLE",
        "CLAUDE_CODE_SKIP_MANTLE_AUTH",
        "DISABLE_PROMPT_CACHING",
        "ENABLE_PROMPT_CACHING_1H",
    )

    def _get_config_env(self, key: str) -> str | None:
        value = self._extra_env.get(key)
        if value:
            return value
        return os.environ.get(key)

    def _is_bedrock_mode(self) -> bool:
        bedrock_flag = self._get_config_env("CLAUDE_CODE_USE_BEDROCK")
        if bedrock_flag is not None:
            return bedrock_flag.strip().lower() not in ("", "0", "false", "no")

        return any(
            self._has_env(key)
            for key in (
                "AWS_BEARER_TOKEN_BEDROCK",
                "ANTHROPIC_AWS_API_KEY",
                "ANTHROPIC_BEDROCK_BASE_URL",
                "ANTHROPIC_BEDROCK_MANTLE_BASE_URL",
                "AWS_ACCESS_KEY_ID",
                "AWS_DEFAULT_PROFILE",
                "AWS_DEFAULT_REGION",
                "AWS_PROFILE",
                "AWS_REGION",
                "CLAUDE_CODE_USE_MANTLE",
            )
        )

    async def exec_as_agent(self, environment, command: str, env=None, **kwargs):
        merged_env = dict(env or {})
        for key in self._passthrough_env:
            if key in self._extra_env:
                merged_env[key] = self._extra_env[key]
            elif key not in merged_env:
                value = os.environ.get(key)
                if value:
                    merged_env[key] = value

        if self._is_bedrock_mode():
            merged_env.setdefault("CLAUDE_CODE_USE_BEDROCK", "1")

        # Only auto-enable Mantle from the URL var when the operator hasn't
        # explicitly opted into either endpoint. A bare CLAUDE_CODE_USE_BEDROCK=1
        # means "Invoke API only" and must not be silently upgraded to dual-mode
        # routing -- otherwise Mantle-shaped model IDs are sent to an endpoint
        # that may not have those models granted, producing 400/403s.
        if (
            merged_env.get("ANTHROPIC_BEDROCK_MANTLE_BASE_URL")
            and self._get_config_env("CLAUDE_CODE_USE_BEDROCK") is None
            and self._get_config_env("CLAUDE_CODE_USE_MANTLE") is None
        ):
            merged_env.setdefault("CLAUDE_CODE_USE_MANTLE", "1")

        if (
            merged_env.get("AWS_REGION") == "us-east-2"
            and not self._get_config_env("AWS_REGION")
            and merged_env.get("AWS_DEFAULT_REGION")
        ):
            merged_env["AWS_REGION"] = merged_env["AWS_DEFAULT_REGION"]

        result = await super().exec_as_agent(
            environment, command, env=merged_env, **kwargs
        )
        if "claude " in command or "$CLAUDE_CONFIG_DIR" in command:
            await super().exec_as_root(
                environment,
                command="chmod -R a+rX /logs/agent 2>/dev/null || true",
            )
        return result


class CodexPreinstalled(_PreinstalledMixin, Codex):
    _preinstalled_check_command = (
        'if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi; '
        "command -v codex && codex --version"
    )

    def __init__(self, *args, **kwargs):
        extra_env = dict(kwargs.get("extra_env", {}) or {})
        self._provider = kwargs.pop(
            "provider",
            extra_env.get("CODEX_MODEL_PROVIDER")
            or os.environ.get("CODEX_MODEL_PROVIDER")
            or "custom",
        )
        self._base_url = kwargs.pop(
            "base_url",
            extra_env.get("OPENAI_BASE_URL") or os.environ.get("OPENAI_BASE_URL"),
        )
        self._env_key = kwargs.pop(
            "env_key",
            extra_env.get("CODEX_PROVIDER_ENV_KEY")
            or os.environ.get("CODEX_PROVIDER_ENV_KEY")
            or "OPENAI_API_KEY",
        )
        self._wire_api = kwargs.pop(
            "wire_api",
            extra_env.get("CODEX_WIRE_API")
            or os.environ.get("CODEX_WIRE_API")
            or "responses",
        )
        self._api_version = kwargs.pop(
            "api_version",
            extra_env.get("AZURE_OPENAI_API_VERSION")
            or os.environ.get("AZURE_OPENAI_API_VERSION"),
        )
        self._verbosity = kwargs.pop(
            "verbosity",
            extra_env.get("CODEX_MODEL_VERBOSITY")
            or os.environ.get("CODEX_MODEL_VERBOSITY")
            or ("medium" if self._base_url else None),
        )
        super().__init__(*args, **kwargs)

    def _resolve_auth_json_path(self):
        if self._base_url or self._get_env("OPENAI_BASE_URL"):
            return None
        return super()._resolve_auth_json_path()

    def build_cli_flags(self) -> str:
        parts = [super().build_cli_flags()]
        base_url = self._base_url or self._get_env("OPENAI_BASE_URL")
        provider = (
            self._provider
            if self._provider != "custom"
            else self._get_env("CODEX_MODEL_PROVIDER") or self._provider
        )
        env_key = self._env_key or self._get_env("CODEX_PROVIDER_ENV_KEY")
        wire_api = self._wire_api or self._get_env("CODEX_WIRE_API")
        api_version = self._api_version or self._get_env("AZURE_OPENAI_API_VERSION")
        verbosity = (
            self._verbosity
            or self._get_env("CODEX_MODEL_VERBOSITY")
            or ("medium" if base_url else None)
        )
        if base_url:
            parts.extend(
                [
                    _codex_config_flag("model_provider", provider),
                    _codex_config_flag(f"model_providers.{provider}.name", provider),
                    _codex_config_flag(
                        f"model_providers.{provider}.base_url", base_url
                    ),
                    _codex_config_flag(
                        f"model_providers.{provider}.env_key", env_key
                    ),
                    _codex_config_flag(
                        f"model_providers.{provider}.wire_api", wire_api
                    ),
                ]
            )
            if api_version:
                parts.append(
                    _codex_config_flag(
                        f"model_providers.{provider}.query_params",
                        {"api-version": api_version},
                    )
                )
        if verbosity:
            parts.append(_codex_config_flag("model_verbosity", verbosity))
        return " ".join(part for part in parts if part)


class OpenCodePreinstalled(_PreinstalledMixin, OpenCode):
    """OpenCode with explicit, artifact-complete same-session continuation.

    Harbor's stock adapter uses ``--continue`` and writes every invocation to
    the same ``opencode.txt`` file.  That is ambiguous when more than one
    session exists and a resumed invocation overwrites the solve stream.  The
    benchmark needs a stronger contract: the post-verifier reflection must be
    another turn in the *exact* session that solved the task, and both phases
    must remain independently auditable.

    This subclass therefore keeps the solve and reflection JSONL streams
    separate, captures the solve session ID, resumes with ``--session``, and
    exports the complete OpenCode session after every phase.  The export is the
    source of truth for the canonical ATIF trajectory because, unlike the
    streaming output, it contains every user turn as well as all assistant
    reasoning/tool records.
    """

    _preinstalled_check_command = (
        'if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi; '
        "command -v opencode && opencode --version"
    )

    _SOLVE_OUTPUT_FILENAME = "opencode.solve.jsonl"
    _REFLECTION_OUTPUT_FILENAME = "opencode.reflection.jsonl"
    _SESSION_EXPORT_FILENAME = "opencode.session.json"
    _TRAJECTORY_FILENAME = "trajectory.json"
    _SOLVE_TRAJECTORY_FILENAME = "trajectory.solve.json"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._opencode_session_id: str | None = None

    @property
    def opencode_session_id(self) -> str | None:
        """The explicit session captured from the initial solve stream."""

        return self._opencode_session_id

    @staticmethod
    def _jsonl_events(text: str) -> list[dict[str, Any]]:
        events: list[dict[str, Any]] = []
        for line in text.splitlines():
            try:
                event = json.loads(line)
            except (json.JSONDecodeError, TypeError):
                continue
            if isinstance(event, dict):
                events.append(event)
        return events

    def _read_phase_events(self, filename: str) -> list[dict[str, Any]]:
        path = self.logs_dir / filename
        if not path.exists():
            return []
        return self._jsonl_events(path.read_text(errors="replace"))

    def _parse_stdout(self) -> list[dict[str, Any]]:
        """Keep Harbor's stdout helpers useful with the split phase files."""

        return self._read_phase_events(
            self._SOLVE_OUTPUT_FILENAME
        ) + self._read_phase_events(self._REFLECTION_OUTPUT_FILENAME)

    @staticmethod
    def _event_session_ids(events: list[dict[str, Any]]) -> set[str]:
        return {
            session_id
            for event in events
            if isinstance(session_id := event.get("sessionID"), str) and session_id
        }

    def _capture_and_validate_session(
        self,
        events: list[dict[str, Any]],
        *,
        resume: bool,
    ) -> str:
        session_ids = self._event_session_ids(events)
        if len(session_ids) != 1:
            phase = "reflection" if resume else "solve"
            raise RuntimeError(
                f"OpenCode {phase} stream must contain exactly one sessionID; "
                f"found {sorted(session_ids)!r}"
            )

        session_id = next(iter(session_ids))
        if resume:
            if not self._opencode_session_id:
                raise RuntimeError(
                    "Cannot resume OpenCode reflection without a captured solve "
                    "sessionID"
                )
            if session_id != self._opencode_session_id:
                raise RuntimeError(
                    "OpenCode reflection escaped the solve session: "
                    f"expected {self._opencode_session_id!r}, got {session_id!r}"
                )
        else:
            self._opencode_session_id = session_id
        return session_id

    @staticmethod
    def _error_messages_from_events(events: list[dict[str, Any]]) -> list[str]:
        messages: list[str] = []
        for event in events:
            if event.get("type") != "error":
                continue
            error = event.get("error")
            if isinstance(error, dict):
                data = error.get("data")
                message = data.get("message") if isinstance(data, dict) else None
                messages.append(str(message or error.get("name") or error))
            else:
                messages.append(str(error))
        return messages

    @staticmethod
    def _timestamp_to_iso(timestamp_ms: Any) -> str | None:
        if not isinstance(timestamp_ms, (int, float)):
            return None
        try:
            return datetime.fromtimestamp(
                timestamp_ms / 1000, tz=timezone.utc
            ).isoformat()
        except (OSError, OverflowError, ValueError):
            return None

    @staticmethod
    def _text_parts(parts: list[Any], part_type: str) -> str:
        return "\n".join(
            text
            for part in parts
            if isinstance(part, dict)
            and part.get("type") == part_type
            and isinstance(text := part.get("text"), str)
        )

    @staticmethod
    def _decode_cli_user_message(text: str) -> str:
        """Undo OpenCode 1.18.3's argv rendering for exported user turns.

        The pinned CLI stores a prompt passed as one positional argument as a
        double-quoted string, escaping embedded double quotes but retaining
        literal newlines. This is not JSON because the newlines remain raw.
        Decode only when a round trip reproduces the export byte-for-byte so a
        genuinely quoted user message cannot be changed accidentally.
        """

        if len(text) < 2 or not text.startswith('"') or not text.endswith('"'):
            return text
        candidate = text[1:-1].replace(r'\"', '"')
        rendered = '"' + candidate.replace('"', r'\"') + '"'
        return candidate if rendered == text else text

    @staticmethod
    def _observation_content(state: dict[str, Any]) -> str | None:
        if "output" in state and state["output"] is not None:
            output = state["output"]
        elif "error" in state and state["error"] is not None:
            output = state["error"]
        else:
            return None
        if isinstance(output, str):
            return output
        return json.dumps(output, ensure_ascii=False, default=str)

    def _validate_export_session(
        self,
        export: dict[str, Any],
    ) -> str:
        info = export.get("info")
        if not isinstance(info, dict) or not isinstance(info.get("id"), str):
            raise RuntimeError("OpenCode export is missing info.id")
        export_session_id = info["id"]
        if not self._opencode_session_id:
            self._opencode_session_id = export_session_id
        if export_session_id != self._opencode_session_id:
            raise RuntimeError(
                "OpenCode export session does not match the solve session: "
                f"expected {self._opencode_session_id!r}, "
                f"got {export_session_id!r}"
            )

        messages = export.get("messages")
        if not isinstance(messages, list):
            raise RuntimeError("OpenCode export is missing messages")
        for message in messages:
            if not isinstance(message, dict):
                raise RuntimeError("OpenCode export contains a non-object message")
            message_info = message.get("info")
            if not isinstance(message_info, dict):
                raise RuntimeError("OpenCode export message is missing info")
            message_session_id = message_info.get("sessionID")
            if message_session_id != export_session_id:
                raise RuntimeError(
                    "OpenCode export contains a message from another session: "
                    f"{message_session_id!r}"
                )
            for part in message.get("parts") or []:
                if not isinstance(part, dict):
                    continue
                part_session_id = part.get("sessionID")
                if part_session_id is not None and part_session_id != export_session_id:
                    raise RuntimeError(
                        "OpenCode export contains a part from another session: "
                        f"{part_session_id!r}"
                    )
        return export_session_id

    def _convert_export_to_trajectory(
        self,
        export: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert an unsanitized OpenCode export into canonical ATIF."""

        session_id = self._validate_export_session(export)
        export_info = export["info"]
        steps: list[dict[str, Any]] = []

        for message in export["messages"]:
            info = message["info"]
            role = info.get("role")
            if role not in ("user", "assistant"):
                continue
            parts = message.get("parts")
            if not isinstance(parts, list):
                parts = []
            timestamp = self._timestamp_to_iso(
                (info.get("time") or {}).get("created")
                if isinstance(info.get("time"), dict)
                else None
            )

            if role == "user":
                step: dict[str, Any] = {
                    "step_id": len(steps) + 1,
                    "source": "user",
                    "message": self._decode_cli_user_message(
                        self._text_parts(parts, "text")
                    ),
                }
                if timestamp:
                    step["timestamp"] = timestamp
                steps.append(step)
                continue

            text = self._text_parts(parts, "text")
            reasoning = self._text_parts(parts, "reasoning")
            tool_calls: list[dict[str, Any]] = []
            observations: list[dict[str, Any]] = []
            for part in parts:
                if not isinstance(part, dict) or part.get("type") != "tool":
                    continue
                state = part.get("state")
                if not isinstance(state, dict):
                    state = {}
                arguments = state.get("input")
                if not isinstance(arguments, dict):
                    arguments = {"value": arguments} if arguments is not None else {}
                call_id = part.get("callID") or part.get("id") or ""
                tool_calls.append(
                    {
                        "tool_call_id": str(call_id),
                        "function_name": str(part.get("tool") or ""),
                        "arguments": arguments,
                    }
                )
                output = self._observation_content(state)
                if output is not None:
                    observations.append(
                        {
                            "source_call_id": str(call_id) or None,
                            "content": output,
                        }
                    )

            tokens = info.get("tokens")
            if not isinstance(tokens, dict):
                tokens = {}
            cache = tokens.get("cache")
            if not isinstance(cache, dict):
                cache = {}
            input_tokens = tokens.get("input", 0) or 0
            output_tokens = tokens.get("output", 0) or 0
            cache_read = cache.get("read", 0) or 0
            cache_write = cache.get("write", 0) or 0
            reasoning_tokens = tokens.get("reasoning", 0) or 0
            cost = info.get("cost", 0) or 0
            metrics: dict[str, Any] = {
                "prompt_tokens": input_tokens + cache_read,
                "completion_tokens": output_tokens,
            }
            if cache_read:
                metrics["cached_tokens"] = cache_read
            if cost:
                metrics["cost_usd"] = cost
            metrics_extra = {
                key: value
                for key, value in {
                    "reasoning_tokens": reasoning_tokens,
                    "cache_write_tokens": cache_write,
                }.items()
                if value
            }
            if metrics_extra:
                metrics["extra"] = metrics_extra

            step = {
                "step_id": len(steps) + 1,
                "source": "agent",
                "message": text,
                "model_name": self.model_name,
                "llm_call_count": 1,
                "metrics": metrics,
            }
            if timestamp:
                step["timestamp"] = timestamp
            if reasoning:
                step["reasoning_content"] = reasoning
            if tool_calls:
                step["tool_calls"] = tool_calls
            if observations:
                step["observation"] = {"results": observations}
            steps.append(step)

        total_tokens = export_info.get("tokens")
        if not isinstance(total_tokens, dict):
            total_tokens = {}
        total_cache = total_tokens.get("cache")
        if not isinstance(total_cache, dict):
            total_cache = {}
        total_cache_read = total_cache.get("read", 0) or 0
        total_input = total_tokens.get("input", 0) or 0
        final_metrics: dict[str, Any] = {
            "total_prompt_tokens": total_input + total_cache_read,
            "total_completion_tokens": total_tokens.get("output", 0) or 0,
            "total_steps": len(steps),
        }
        if total_cache_read:
            final_metrics["total_cached_tokens"] = total_cache_read
        if export_info.get("cost"):
            final_metrics["total_cost_usd"] = export_info["cost"]

        return {
            "schema_version": "ATIF-v1.7",
            "session_id": session_id,
            "agent": {
                "name": "opencode",
                "version": str(
                    export_info.get("version") or self.version() or "unknown"
                ),
                "model_name": self.model_name,
            },
            "steps": steps,
            "final_metrics": final_metrics,
        }

    def _trajectory_from_export_file(self) -> dict[str, Any]:
        export_path = self.logs_dir / self._SESSION_EXPORT_FILENAME
        if not export_path.exists():
            raise RuntimeError(f"OpenCode session export is missing: {export_path}")
        try:
            export = json.loads(export_path.read_text())
        except json.JSONDecodeError as exc:
            raise RuntimeError("OpenCode session export is not valid JSON") from exc
        if not isinstance(export, dict):
            raise RuntimeError("OpenCode session export must be a JSON object")
        return self._convert_export_to_trajectory(export)

    def _write_canonical_trajectory(
        self,
        *,
        preserve_as_solve: bool = False,
    ) -> dict[str, Any]:
        trajectory = self._trajectory_from_export_file()
        serialized = json.dumps(trajectory, indent=2, ensure_ascii=False) + "\n"
        (self.logs_dir / self._TRAJECTORY_FILENAME).write_text(serialized)
        if preserve_as_solve:
            (self.logs_dir / self._SOLVE_TRAJECTORY_FILENAME).write_text(serialized)
        return trajectory

    def populate_context_post_run(self, context) -> None:
        # Harbor calls this once immediately after the solve phase.  On a
        # non-mounted backend this is the first point where the export is
        # locally available, so preserve the solve-only view here as well.
        preserve_as_solve = not (
            self.logs_dir / self._REFLECTION_OUTPUT_FILENAME
        ).exists()
        trajectory = self._write_canonical_trajectory(
            preserve_as_solve=preserve_as_solve
        )
        final_metrics = trajectory["final_metrics"]
        context.cost_usd = final_metrics.get("total_cost_usd")
        context.n_input_tokens = final_metrics.get("total_prompt_tokens", 0)
        context.n_output_tokens = final_metrics.get("total_completion_tokens", 0)
        context.n_cache_tokens = final_metrics.get("total_cached_tokens", 0)

    def _provider_environment(self, provider: str) -> dict[str, str]:
        provider_keys = {
            "amazon-bedrock": (
                "AWS_ACCESS_KEY_ID",
                "AWS_SECRET_ACCESS_KEY",
                "AWS_REGION",
            ),
            "anthropic": ("ANTHROPIC_API_KEY",),
            "azure": ("AZURE_RESOURCE_NAME", "AZURE_API_KEY"),
            "deepseek": ("DEEPSEEK_API_KEY",),
            "github-copilot": ("GITHUB_TOKEN",),
            "google": (
                "GEMINI_API_KEY",
                "GOOGLE_GENERATIVE_AI_API_KEY",
                "GOOGLE_APPLICATION_CREDENTIALS",
                "GOOGLE_CLOUD_PROJECT",
                "GOOGLE_CLOUD_LOCATION",
                "GOOGLE_GENAI_USE_VERTEXAI",
                "GOOGLE_API_KEY",
            ),
            "groq": ("GROQ_API_KEY",),
            "huggingface": ("HF_TOKEN",),
            "llama": ("LLAMA_API_KEY",),
            "mistral": ("MISTRAL_API_KEY",),
            "openai": ("OPENAI_API_KEY", "OPENAI_BASE_URL"),
            "opencode": ("OPENCODE_API_KEY",),
            "xai": ("XAI_API_KEY",),
            "openrouter": ("OPENROUTER_API_KEY",),
        }
        env = {
            key: os.environ[key]
            for key in provider_keys.get(provider, ())
            if key in os.environ
        }
        env.update(
            {
                "OPENCODE_FAKE_VCS": "git",
                "XDG_DATA_HOME": "/logs/agent/opencode/xdg-data",
                "XDG_STATE_HOME": "/logs/agent/opencode/xdg-state",
            }
        )
        return env

    async def _export_session(
        self,
        environment: BaseEnvironment,
        env: dict[str, str],
        session_id: str,
        *,
        resume: bool,
    ) -> None:
        await self.exec_as_agent(
            environment,
            command=(
                ". ~/.nvm/nvm.sh; "
                f"opencode export {shlex.quote(session_id)} "
                f"> /logs/agent/{self._SESSION_EXPORT_FILENAME}"
            ),
            env=env,
        )

        # Bind-mounted Harbor environments expose /logs/agent immediately.
        # Non-mounted backends generate the trajectory later, after Harbor has
        # downloaded this export and calls populate_context_post_run().
        if (self.logs_dir / self._SESSION_EXPORT_FILENAME).exists():
            self._write_canonical_trajectory(preserve_as_solve=not resume)

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context,
    ) -> None:
        self._instruction = instruction
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        provider, _ = self.model_name.split("/", 1)
        env = self._provider_environment(provider)

        skills_command = self._build_register_skills_command()
        if skills_command:
            await self.exec_as_agent(environment, command=skills_command, env=env)
        config_command = self._build_register_config_command()
        if config_command:
            await self.exec_as_agent(environment, command=config_command, env=env)

        resume = bool(self._resume)
        if resume and not self._opencode_session_id:
            raise RuntimeError(
                "Cannot resume OpenCode reflection before the solve sessionID "
                "has been captured"
            )
        resume_flag = (
            f"--session {shlex.quote(self._opencode_session_id)} " if resume else ""
        )
        phase_filename = (
            self._REFLECTION_OUTPUT_FILENAME if resume else self._SOLVE_OUTPUT_FILENAME
        )
        cli_flags = self.build_cli_flags()
        cli_flags_arg = f"{cli_flags} " if cli_flags else ""

        result = await self.exec_as_agent(
            environment,
            command=(
                ". ~/.nvm/nvm.sh; "
                f"opencode --model={shlex.quote(self.model_name)} "
                "run --format=json "
                f"{resume_flag}{cli_flags_arg}--thinking "
                "--dangerously-skip-permissions -- "
                f"{shlex.quote(instruction)} "
                "2>&1 </dev/null | stdbuf -oL "
                f"tee /logs/agent/{phase_filename}"
            ),
            env=env,
        )

        # ``exec`` output may be truncated by the environment/transport.  The
        # tee file is the complete per-phase audit stream when logs are bind
        # mounted, so make it authoritative and retain stdout only for
        # backends where that file is not locally visible yet.
        events = self._read_phase_events(phase_filename)
        if not events:
            events = self._jsonl_events(str(getattr(result, "stdout", "") or ""))
        session_id = self._capture_and_validate_session(events, resume=resume)
        await self._export_session(
            environment,
            env,
            session_id,
            resume=resume,
        )

        if messages := self._error_messages_from_events(events):
            raise NonZeroAgentExitCodeError(
                "OpenCode emitted error event(s): " + "; ".join(messages[:3])
            )


class GeminiCliPreinstalled(_PreinstalledMixin, GeminiCli):
    _preinstalled_check_command = (
        'if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi; '
        "command -v gemini && gemini --version"
    )

    def __init__(self, *args, **kwargs):
        extra_env = dict(kwargs.pop("extra_env", {}) or {})
        extra_env.setdefault("GEMINI_CLI_TRUST_WORKSPACE", "true")
        super().__init__(*args, extra_env=extra_env, **kwargs)

    def _convert_gemini_jsonl_trajectory(self, jsonl_path) -> dict[str, Any]:
        metadata: dict[str, Any] = {}
        messages: dict[str, dict[str, Any]] = {}

        for line in jsonl_path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                record = json.loads(line)
            except json.JSONDecodeError:
                continue

            rewind_to = record.get("$rewindTo")
            if isinstance(rewind_to, str):
                message_ids = list(messages)
                if rewind_to in messages:
                    for message_id in message_ids[message_ids.index(rewind_to) :]:
                        messages.pop(message_id, None)
                else:
                    messages.clear()
                continue

            message_id = record.get("id")
            if isinstance(message_id, str):
                messages[message_id] = record
                continue

            metadata_update = record.get("$set")
            if isinstance(metadata_update, dict):
                metadata.update(metadata_update)
                continue

            if isinstance(record.get("sessionId"), str):
                metadata.update(record)

        metadata["messages"] = list(messages.values())
        return metadata

    def populate_context_post_run(self, context) -> None:
        json_path = self.logs_dir / "gemini-cli.trajectory.json"
        jsonl_path = self.logs_dir / "gemini-cli.trajectory.jsonl"

        if not json_path.exists() and jsonl_path.exists():
            try:
                trajectory = self._convert_gemini_jsonl_trajectory(jsonl_path)
                json_path.write_text(json.dumps(trajectory, indent=2))
            except Exception as exc:
                self.logger.debug(f"Error converting Gemini JSONL trajectory: {exc}")

        super().populate_context_post_run(context)

    @with_prompt_template
    async def run(self, instruction: str, environment: BaseEnvironment, context) -> None:
        escaped_instruction = shlex.quote(instruction)

        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in the format provider/model_name")

        model = self.model_name.split("/")[-1]

        env = {}
        auth_vars = [
            "GEMINI_API_KEY",
            "GOOGLE_APPLICATION_CREDENTIALS",
            "GOOGLE_CLOUD_PROJECT",
            "GOOGLE_CLOUD_LOCATION",
            "GOOGLE_GENAI_USE_VERTEXAI",
            "GOOGLE_API_KEY",
        ]
        for var in auth_vars:
            value = self._get_env(var)
            if value:
                env[var] = value

        skills_command = self._build_register_skills_command()
        if skills_command:
            await self.exec_as_agent(environment, command=skills_command, env=env)

        # Harbor's GeminiCli base class doesn't expose
        # _build_register_mcp_servers_command (Gemini's MCP wiring lives in
        # ~/.gemini/settings.json, not a CLI subcommand). Guard with hasattr
        # so future Harbor versions that add it pick up automatically.
        if hasattr(self, "_build_register_mcp_servers_command"):
            mcp_command = self._build_register_mcp_servers_command()
            if mcp_command:
                await self.exec_as_agent(environment, command=mcp_command, env=env)

        cli_flags = self.build_cli_flags()
        extra_flags = (cli_flags + " ") if cli_flags else ""

        try:
            await self.exec_as_agent(
                environment,
                command=(
                    ". ~/.nvm/nvm.sh; "
                    f"gemini --yolo {extra_flags}--model={model} "
                    f"--prompt={escaped_instruction} "
                    f"2>&1 </dev/null | stdbuf -oL tee /logs/agent/gemini-cli.txt"
                ),
                env=env,
            )
        finally:
            try:
                await self.exec_as_agent(
                    environment,
                    command=(
                        "latest_jsonl=$(find ~/.gemini/tmp -type f "
                        "\\( -path '*/chats/session-*.jsonl' "
                        "-o -name 'session-*.jsonl' \\) "
                        "-printf '%T@ %p\\n' 2>/dev/null | "
                        "sort -nr | head -n 1 | cut -d' ' -f2-); "
                        'if [ -n "$latest_jsonl" ]; then '
                        'cp "$latest_jsonl" '
                        "/logs/agent/gemini-cli.trajectory.jsonl; "
                        "else "
                        "find ~/.gemini/tmp -type f -name 'session-*.json' "
                        "2>/dev/null | head -n 1 | xargs -r -I{} "
                        "cp {} /logs/agent/gemini-cli.trajectory.json; "
                        "fi"
                    ),
                )
            except Exception:
                pass


class KimiCliPreinstalled(_PreinstalledMixin, KimiCli):
    # Inject the venv-bin paths Harbor's exec_as_agent doesn't inherit
    # from the image's ENV PATH. Without this, the check fails inside the
    # trial container, triggers super().install() (apt + uv tool install),
    # which then exits 2 on `kimi --version` for unrelated reasons.
    _preinstalled_check_command = (
        'export PATH="/root/.local/bin:/usr/local/bin:$PATH"; '
        "command -v kimi && kimi --version"
    )

    def __init__(self, *args, **kwargs):
        if "base_url" not in kwargs and os.environ.get("KIMI_BEDROCK_BASE_URL"):
            kwargs["base_url"] = os.environ["KIMI_BEDROCK_BASE_URL"]
        if "api_key" not in kwargs and os.environ.get("KIMI_BEDROCK_API_KEY"):
            kwargs["api_key"] = os.environ["KIMI_BEDROCK_API_KEY"]
        super().__init__(*args, **kwargs)

    @with_prompt_template
    async def run(self, instruction: str, environment: BaseEnvironment, context) -> None:
        if not self.model_name or "/" not in self.model_name:
            raise ValueError("Model name must be in format provider/model_name")

        provider, model = self.model_name.split("/", 1)
        pcfg = _PROVIDER_CONFIG.get(provider)
        if pcfg is None:
            raise ValueError(
                f"Unsupported provider '{provider}' for kimi-cli. "
                f"Supported: {sorted(_PROVIDER_CONFIG)}"
            )

        base_url = self._base_url or pcfg["base_url"]
        config_json = json.dumps(
            {
                "default_model": "model",
                "default_yolo": True,
                "providers": {
                    "harbor": {
                        "type": pcfg["type"],
                        "base_url": base_url,
                        "api_key": "",
                    }
                },
                "models": {
                    "model": {
                        "provider": "harbor",
                        "model": model,
                        "max_context_size": self._max_context_size,
                    }
                },
            }
        )
        escaped_config = shlex.quote(config_json)

        prompt_request = json.dumps(
            {
                "jsonrpc": "2.0",
                "method": "prompt",
                "id": "1",
                "params": {"user_input": instruction},
            }
        )
        escaped_prompt = shlex.quote(prompt_request)

        env: dict[str, str] = {}
        for key in pcfg.get("env_keys", []):
            value = self._get_env(key)
            if value:
                env[key] = value

        if self._api_key:
            env[pcfg["env_keys"][0]] = self._api_key

        if provider == "openai":
            env["OPENAI_BASE_URL"] = base_url

        setup_parts = [f"echo {escaped_config} > /tmp/kimi-config.json"]

        skills_cmd = self._build_register_skills_command()
        if skills_cmd:
            setup_parts.append(skills_cmd)

        mcp_cmd = self._build_register_mcp_servers_command()
        if mcp_cmd:
            setup_parts.append(mcp_cmd)

        await self.exec_as_agent(environment, command=" && ".join(setup_parts), env=env)

        mcp_flag = "--mcp-config-file /tmp/kimi-mcp.json " if mcp_cmd else ""
        run_command = (
            f'export PATH="$HOME/.local/bin:$PATH"; '
            f"(echo {escaped_prompt}; sleep 86400) | "
            f"kimi --config-file /tmp/kimi-config.json --wire --yolo "
            f"{mcp_flag}"
            f"2>/dev/null | ("
            f"while IFS= read -r line; do "
            f'echo "$line" >> /logs/agent/{_OUTPUT_FILENAME}; '
            'case "$line" in *\'"id":"1"\'*) break ;; esac; '
            f"done; kill 0 2>/dev/null)"
        )

        try:
            await self.exec_as_agent(environment, command=run_command, env=env)
        except NonZeroAgentExitCodeError as exc:
            if "exit 143" not in str(exc):
                raise
