#!/usr/bin/env bash
set -euo pipefail

: "${NODE_VERSION:=22}"
: "${NVM_VERSION:=v0.40.2}"
: "${CLAUDE_CODE_VERSION:=latest}"
: "${GEMINI_CLI_VERSION:=latest}"
: "${CODEX_CLI_VERSION:=latest}"
: "${KIMI_CLI_VERSION:=latest}"
: "${OPENCLAW_VERSION:=latest}"

export HOME="${HOME:-/root}"
export DEBIAN_FRONTEND="${DEBIAN_FRONTEND:-noninteractive}"
export NVM_DIR="${NVM_DIR:-$HOME/.nvm}"
export PATH="/root/.local/bin:/usr/local/bin:/usr/bin:/bin:${PATH:-}"
export PIP_DISABLE_PIP_VERSION_CHECK="${PIP_DISABLE_PIP_VERSION_CHECK:-1}"
export PIP_NO_CACHE_DIR="${PIP_NO_CACHE_DIR:-1}"
export OPENCLAW_PLUGIN_STAGE_DIR="${OPENCLAW_PLUGIN_STAGE_DIR:-/opt/openclaw-plugin-stage}"

configure_apt_mirror() {
  # Switch to the EC2-internal Ubuntu mirror in us-east-1 -- archive.ubuntu.com
  # routes over the public internet and frequently times out from AWS, which
  # made `apt-get install nodejs npm` in per-task Dockerfiles hang for 10+ min.
  # ec2.archive.ubuntu.com is on the AWS backbone (no egress charge, ~100MB/s).
  # Ubuntu 24.04 (noble) uses the new deb822 format under
  # /etc/apt/sources.list.d/ubuntu.sources; older releases keep sources.list.
  local mirror="http://us-east-1.ec2.archive.ubuntu.com/ubuntu"
  if [ -f /etc/apt/sources.list.d/ubuntu.sources ]; then
    sed -i \
      -e "s|http://archive.ubuntu.com/ubuntu|$mirror|g" \
      -e "s|http://security.ubuntu.com/ubuntu|$mirror|g" \
      /etc/apt/sources.list.d/ubuntu.sources
  fi
  if [ -f /etc/apt/sources.list ]; then
    sed -i \
      -e "s|http://archive.ubuntu.com/ubuntu|$mirror|g" \
      -e "s|http://security.ubuntu.com/ubuntu|$mirror|g" \
      /etc/apt/sources.list
  fi
}

install_system_packages() {
  configure_apt_mirror
  apt-get update
  # nodejs + npm are pre-installed here so per-task Dockerfiles that
  # `apt install nodejs npm` (~27 of them) hit the apt cache instead of
  # re-downloading ~150MB. Ubuntu's apt nodejs (v18) coexists with the
  # NVM-installed v22 below; PATH ordering keeps v22 the default.
  apt-get install -y --no-install-recommends \
    bash \
    ca-certificates \
    curl \
    git \
    jq \
    nodejs \
    npm \
    python3 \
    python3-pip \
    python3-venv \
    ripgrep \
    xz-utils
  rm -rf /var/lib/apt/lists/*
}

ensure_nvm() {
  if [ ! -s "$NVM_DIR/nvm.sh" ]; then
    rm -rf "$NVM_DIR"
    git clone --branch "$NVM_VERSION" --depth 1 https://github.com/nvm-sh/nvm.git "$NVM_DIR"
  fi

  # shellcheck source=/dev/null
  . "$NVM_DIR/nvm.sh"
  command -v nvm >/dev/null 2>&1 || {
    echo "Error: nvm failed to load" >&2
    exit 1
  }

  nvm install "$NODE_VERSION"
  nvm use "$NODE_VERSION"
  nvm alias default "$NODE_VERSION"

  npm config set update-notifier false
  npm config set fund false
  npm config set audit false
}

npm_install_global() {
  local package_name="$1"
  local package_version="$2"

  if [ -z "$package_version" ] || [ "$package_version" = "latest" ]; then
    npm install -g "${package_name}@latest"
  else
    npm install -g "${package_name}@${package_version}"
  fi
}

link_binary() {
  local name="$1"
  local bin_path

  bin_path="$(command -v "$name" 2>/dev/null || true)"
  if [ -z "$bin_path" ]; then
    return 0
  fi

  mkdir -p "$HOME/.local/bin"
  ln -sf "$bin_path" "$HOME/.local/bin/$name"
  ln -sf "$bin_path" "/usr/local/bin/$name"
}

configure_gemini_settings() {
  mkdir -p "$HOME/.gemini"
  # ``includeDirectories`` expands Gemini-CLI's workspace allowlist so the
  # agent's read_file / list_directory tools can access skill mount points
  # outside /root/task. Without this, Gemini-CLI rejects every read of the
  # mounted SKILL.md with "Path not in workspace" -- even though startup
  # discovery (which uses Gemini's own native loader) DOES find the skill.
  # The 5 paths mirror the bind-mount targets in
  # skillevolbench/harbor_ext/env.py:178-184.
  cat > "$HOME/.gemini/settings.json" <<'EOF'
{
  "experimental": {
    "skills": true
  },
  "context": {
    "includeDirectories": [
      "/skills",
      "/root/.gemini/skills",
      "/root/.agents/skills",
      "/root/.claude/skills",
      "/root/.kimi/skills"
    ]
  },
  "tools": {
    "exclude": [
      "update_topic"
    ]
  }
}
EOF
}

resolve_kimi_bin_path() {
  local venv_dir="$HOME/.local/share/kimi-cli-venv"
  local script_name

  if [ ! -x "$venv_dir/bin/python" ]; then
    return 1
  fi

  script_name="$("$venv_dir/bin/python" - <<'PY'
import importlib.metadata as md

try:
    dist = md.distribution("kimi-cli")
except md.PackageNotFoundError:
    print("")
    raise SystemExit(0)

names = [ep.name for ep in dist.entry_points if ep.group == "console_scripts"]
for preferred in ("kimi", "kimi-cli"):
    if preferred in names:
        print(preferred)
        break
else:
    print(names[0] if names else "")
PY
)"

  if [ -n "$script_name" ] && [ -x "$venv_dir/bin/$script_name" ]; then
    printf '%s\n' "$venv_dir/bin/$script_name"
    return 0
  fi

  return 1
}

install_kimi_cli() {
  local venv_dir="$HOME/.local/share/kimi-cli-venv"
  local kimi_bin

  rm -rf "$venv_dir"
  python3 -m venv "$venv_dir"

  if [ -z "$KIMI_CLI_VERSION" ] || [ "$KIMI_CLI_VERSION" = "latest" ]; then
    "$venv_dir/bin/pip" install --upgrade --prefer-binary kimi-cli
  else
    "$venv_dir/bin/pip" install --upgrade --prefer-binary "kimi-cli==$KIMI_CLI_VERSION"
  fi

  kimi_bin="$(resolve_kimi_bin_path)"
  if [ -z "$kimi_bin" ]; then
    echo "Error: could not resolve kimi-cli entry point" >&2
    exit 1
  fi

  mkdir -p "$HOME/.local/bin"
  ln -sf "$kimi_bin" "$HOME/.local/bin/kimi"
  ln -sf "$kimi_bin" /usr/local/bin/kimi
}

prewarm_openclaw() {
  local state_dir="/tmp/openclaw-doctor"
  local workspace_dir="$state_dir/workspace"

  rm -rf "$state_dir"
  mkdir -p "$OPENCLAW_PLUGIN_STAGE_DIR" "$workspace_dir"
  OPENCLAW_STATE_DIR="$state_dir" \
    OPENCLAW_CONFIG_PATH="$state_dir/openclaw.json" \
    openclaw --no-color doctor --non-interactive --repair --yes
  OPENCLAW_STATE_DIR="$state_dir" \
    OPENCLAW_CONFIG_PATH="$state_dir/openclaw.json" \
    openclaw --no-color setup --workspace "$workspace_dir"
  OPENCLAW_STATE_DIR="$state_dir" \
    OPENCLAW_CONFIG_PATH="$state_dir/openclaw.json" \
    openclaw --no-color models set google/gemini-3.1-flash-lite-preview
  OPENCLAW_STATE_DIR="$state_dir" \
    OPENCLAW_CONFIG_PATH="$state_dir/openclaw.json" \
    openclaw --no-color agent --local --agent main --message "prewarm" --json --timeout 5 >/tmp/openclaw-prewarm-agent.log 2>&1 || true
  rm -rf "$state_dir"
}

cleanup_caches() {
  npm cache clean --force >/dev/null 2>&1 || true
  rm -rf "$HOME/.cache/pip" "$HOME/.npm/_cacache"
}

verify_installations() {
  node --version
  npm --version
  claude --version
  gemini --version
  codex --version
  kimi --version
  openclaw --version
}

install_system_packages
ensure_nvm

npm_install_global "@anthropic-ai/claude-code" "$CLAUDE_CODE_VERSION"
npm_install_global "@google/gemini-cli" "$GEMINI_CLI_VERSION"
npm_install_global "@openai/codex" "$CODEX_CLI_VERSION"
npm_install_global "openclaw" "$OPENCLAW_VERSION"

configure_gemini_settings
link_binary node
link_binary npm
link_binary npx
link_binary claude
link_binary gemini
link_binary codex
link_binary openclaw

prewarm_openclaw
install_kimi_cli
cleanup_caches
verify_installations
