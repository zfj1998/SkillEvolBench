import json
import shlex
from typing import Any

from harbor.agents.installed.base import BaseInstalledAgent, CliFlag, with_prompt_template
from harbor.environments.base import BaseEnvironment
from harbor.models.agent.context import AgentContext


class OpenClaw(BaseInstalledAgent):
    """Harbor adapter for the OpenClaw CLI."""

    _OUTPUT_FILENAME = "openclaw.txt"
    _JSON_FILENAME = "openclaw-result.json"

    CLI_FLAGS = [
        CliFlag(
            "thinking",
            cli="--thinking",
            type="enum",
            choices=["off", "minimal", "low", "medium", "high", "xhigh"],
        ),
    ]

    def __init__(
        self,
        *args: Any,
        state_dir: str = "/tmp/openclaw-harbor",
        workspace: str = "/root/task",
        agent_id: str = "main",
        setup_workspace: bool = True,
        **kwargs: Any,
    ):
        super().__init__(*args, **kwargs)
        self._state_dir = state_dir
        self._workspace = workspace
        self._agent_id = agent_id
        self._setup_workspace = setup_workspace

    @staticmethod
    def name() -> str:
        return "openclaw"

    def get_version_command(self) -> str | None:
        return (
            'if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi; '
            "openclaw --version"
        )

    def parse_version(self, stdout: str) -> str:
        return stdout.strip().splitlines()[-1].strip()

    async def install(self, environment: BaseEnvironment) -> None:
        check = (
            'if [ -s "$HOME/.nvm/nvm.sh" ]; then . "$HOME/.nvm/nvm.sh"; fi; '
            "command -v openclaw >/dev/null && openclaw --version"
        )
        try:
            await self.exec_as_agent(environment, command=check)
            return
        except Exception:
            pass

        version_spec = f"@{self._version}" if self._version else "@latest"
        await self.exec_as_agent(
            environment,
            command=(
                "set -euo pipefail; "
                'export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"; '
                'if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi; '
                f"npm install -g openclaw{version_spec}; "
                "openclaw --version"
            ),
        )

    def _model_for_openclaw(self) -> str:
        if not self.model_name:
            return "google/gemini-3.1-flash-lite-preview"
        if self.model_name.startswith("gemini/"):
            return "google/" + self.model_name.split("/", 1)[1]
        return self.model_name

    def _openclaw_env(self) -> dict[str, str]:
        env: dict[str, str] = {
            "OPENCLAW_STATE_DIR": self._state_dir,
            "OPENCLAW_CONFIG_PATH": f"{self._state_dir}/openclaw.json",
            "OPENCLAW_PLUGIN_STAGE_DIR": "/opt/openclaw-plugin-stage",
        }
        for key in [
            "ANTHROPIC_API_KEY",
            "GEMINI_API_KEY",
            "GOOGLE_API_KEY",
            "GOOGLE_GENERATIVE_AI_API_KEY",
            "OPENAI_API_KEY",
            "OPENROUTER_API_KEY",
            "XAI_API_KEY",
            "GITHUB_TOKEN",
        ]:
            value = self._get_env(key)
            if value:
                env[key] = value
        if "GEMINI_API_KEY" in env and "GOOGLE_API_KEY" not in env:
            env["GOOGLE_API_KEY"] = env["GEMINI_API_KEY"]
        return env

    def _shell_prefix(self) -> str:
        return (
            'export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"; '
            'if [ -s "$NVM_DIR/nvm.sh" ]; then . "$NVM_DIR/nvm.sh"; fi; '
            f"mkdir -p {shlex.quote(self._state_dir)}; "
            f"export OPENCLAW_STATE_DIR={shlex.quote(self._state_dir)}; "
            f"export OPENCLAW_CONFIG_PATH={shlex.quote(self._state_dir + '/openclaw.json')}; "
        )

    def _write_auth_profiles_command(self) -> str:
        agent_dir = f"{self._state_dir}/agents/{self._agent_id}/agent"
        auth_path = f"{agent_dir}/auth-profiles.json"
        return (
            f"mkdir -p {shlex.quote(agent_dir)}; "
            "python3 - <<'PY'\n"
            "import json\n"
            "import os\n"
            f"auth_path = {auth_path!r}\n"
            "profiles = {}\n"
            "def add(profile_id, provider, env_names):\n"
            "    for env_name in env_names:\n"
            "        value = os.environ.get(env_name)\n"
            "        if value:\n"
            "            profiles[profile_id] = {\n"
            "                'type': 'api_key',\n"
            "                'provider': provider,\n"
            "                'key': value,\n"
            "                'displayName': 'Harbor env',\n"
            "            }\n"
            "            return\n"
            "add('anthropic:harbor-env', 'anthropic', ['ANTHROPIC_API_KEY'])\n"
            "add('google:harbor-env', 'google', ['GOOGLE_API_KEY', 'GEMINI_API_KEY', 'GOOGLE_GENERATIVE_AI_API_KEY'])\n"
            "add('openai:harbor-env', 'openai', ['OPENAI_API_KEY'])\n"
            "add('openrouter:harbor-env', 'openrouter', ['OPENROUTER_API_KEY'])\n"
            "add('xai:harbor-env', 'xai', ['XAI_API_KEY'])\n"
            "if profiles:\n"
            "    with open(auth_path, 'w', encoding='utf-8') as f:\n"
            "        json.dump({'version': 1, 'profiles': profiles}, f)\n"
            "PY\n"
        )

    async def _configure_openclaw(self, environment: BaseEnvironment, env: dict[str, str]) -> None:
        model = shlex.quote(self._model_for_openclaw())
        workspace = shlex.quote(self._workspace)
        setup_cmd = (
            self._shell_prefix()
            + (
                f"openclaw setup --workspace {workspace}; "
                if self._setup_workspace
                else 'test -f "$OPENCLAW_CONFIG_PATH" || openclaw setup; '
            )
            + "openclaw config set env.shellEnv.enabled true --strict-json; "
            + f"openclaw models set {model}; "
            + self._write_auth_profiles_command()
            + "openclaw config validate"
        )
        await self.exec_as_agent(environment, command=setup_cmd, env=env, cwd=self._workspace)

    @with_prompt_template
    async def run(
        self,
        instruction: str,
        environment: BaseEnvironment,
        context: AgentContext,
    ) -> None:
        env = self._openclaw_env()
        await self._configure_openclaw(environment, env)

        escaped_instruction = shlex.quote(instruction)
        escaped_agent = shlex.quote(self._agent_id)
        cli_flags = self.build_cli_flags()
        extra_flags = (cli_flags + " ") if cli_flags else ""
        output_path = f"/logs/agent/{self._OUTPUT_FILENAME}"
        json_path = f"/logs/agent/{self._JSON_FILENAME}"

        command = (
            self._shell_prefix()
            + "set -o pipefail; "
            + f"openclaw --no-color agent --local --agent {escaped_agent} "
            + f"--message {escaped_instruction} "
            + f"{extra_flags}--json "
            + "2>&1 </dev/null "
            + f"| stdbuf -oL tee {output_path}; "
            + "python3 - <<'PY'\n"
            + "import json\n"
            + f"p = {output_path!r}\n"
            + f"out = {json_path!r}\n"
            + "text = open(p, encoding='utf-8', errors='replace').read()\n"
            + "decoder = json.JSONDecoder()\n"
            + "for i, ch in enumerate(text):\n"
            + "    if ch != '{':\n"
            + "        continue\n"
            + "    try:\n"
            + "        obj, _ = decoder.raw_decode(text[i:])\n"
            + "    except json.JSONDecodeError:\n"
            + "        continue\n"
            + "    open(out, 'w', encoding='utf-8').write(json.dumps(obj, indent=2))\n"
            + "    break\n"
            + "PY\n"
        )

        await self.exec_as_agent(environment, command=command, env=env, cwd=self._workspace)

    def populate_context_post_run(self, context: AgentContext) -> None:
        result_file = self.logs_dir / self._JSON_FILENAME
        if not result_file.exists():
            return

        try:
            result = json.loads(result_file.read_text())
        except json.JSONDecodeError:
            return

        meta = result.get("meta") or {}
        agent_meta = meta.get("agentMeta") or {}
        usage = agent_meta.get("usage") or agent_meta.get("lastCallUsage") or {}

        input_tokens = usage.get("input") or usage.get("promptTokens") or 0
        output_tokens = usage.get("output") or 0
        cache_read = usage.get("cacheRead") or 0
        cache_write = usage.get("cacheWrite") or 0

        context.n_input_tokens = int(input_tokens) + int(cache_read)
        context.n_output_tokens = int(output_tokens)
        context.n_cache_tokens = int(cache_read) + int(cache_write)
