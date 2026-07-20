# Agent Build Image

This image preinstalls the CLIs that Harbor agents may need:

- Claude Code
- Gemini CLI
- Codex CLI
- Kimi CLI
- OpenClaw

It uses `nvm` under `/root/.nvm` and defaults to `NODE_VERSION=22`, so
`nvm` resolves the current Node 22 release at build time. Installed commands are
linked into `/usr/local/bin` for Harbor to invoke directly.

OpenClaw runtime dependencies are prewarmed under `/opt/openclaw-plugin-stage`
to avoid repeated per-task plugin staging during Harbor runs.

`AGENT_CLI_SET` can restrict the image to a comma- or space-separated subset
of `claude-code`, `gemini-cli`, `codex`, `kimi-cli`, and `openclaw`. Its default
is `all`; AP's Codex-only smoke uses `codex` to avoid downloading unrelated
agent runtimes. `APT_MIRROR` is also configurable because the AWS-local default
is not reachable efficiently from every execution cluster.

Build with Docker:

```bash
docker/agent-build/build.sh
```

Build with Podman:

```bash
CONTAINER_BUILDER=podman docker/agent-build/build.sh
```

Pin versions when needed:

```bash
NODE_VERSION=22 \
CLAUDE_CODE_VERSION=latest \
GEMINI_CLI_VERSION=latest \
CODEX_CLI_VERSION=latest \
KIMI_CLI_VERSION=latest \
OPENCLAW_VERSION=latest \
AGENT_CLI_SET=codex \
APT_MIRROR=http://mirrors.aliyun.com/ubuntu \
docker/agent-build/build.sh
```

The image only installs CLI tools. Provider API keys and model choices should
still be supplied at runtime through environment variables or Harbor config.
