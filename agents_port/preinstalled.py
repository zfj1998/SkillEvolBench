import json
import os
import shlex
from typing import Any

from harbor.agents.installed.claude_code import ClaudeCode
from harbor.agents.installed.codex import Codex
from harbor.agents.installed.gemini_cli import GeminiCli
from harbor.agents.installed.kimi_cli import KimiCli, _OUTPUT_FILENAME, _PROVIDER_CONFIG
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
