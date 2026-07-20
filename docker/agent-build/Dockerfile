FROM ubuntu:24.04

ARG NODE_VERSION=22
ARG NVM_VERSION=v0.40.2
ARG CLAUDE_CODE_VERSION=latest
ARG GEMINI_CLI_VERSION=latest
ARG CODEX_CLI_VERSION=latest
ARG OPENCODE_VERSION=1.18.3
ARG KIMI_CLI_VERSION=latest
ARG OPENCLAW_VERSION=latest
ARG APT_MIRROR=http://us-east-1.ec2.archive.ubuntu.com/ubuntu
ARG AGENT_CLI_SET=all

ENV DEBIAN_FRONTEND=noninteractive \
    HOME=/root \
    NVM_DIR=/root/.nvm \
    NODE_ENV=production \
    NPM_CONFIG_UPDATE_NOTIFIER=false \
    NPM_CONFIG_FUND=false \
    NPM_CONFIG_AUDIT=false \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1 \
    OPENCLAW_PLUGIN_STAGE_DIR=/opt/openclaw-plugin-stage \
    AGENT_RUNTIME=1 \
    AGENT_RUNTIME_IMAGE=agent-runtime

ENV PATH=/root/.local/bin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

COPY install-agent-runtime.sh /tmp/install-agent-runtime.sh

RUN chmod +x /tmp/install-agent-runtime.sh \
    && NODE_VERSION="$NODE_VERSION" \
       NVM_VERSION="$NVM_VERSION" \
       CLAUDE_CODE_VERSION="$CLAUDE_CODE_VERSION" \
       GEMINI_CLI_VERSION="$GEMINI_CLI_VERSION" \
       CODEX_CLI_VERSION="$CODEX_CLI_VERSION" \
       OPENCODE_VERSION="$OPENCODE_VERSION" \
       KIMI_CLI_VERSION="$KIMI_CLI_VERSION" \
       OPENCLAW_VERSION="$OPENCLAW_VERSION" \
       APT_MIRROR="$APT_MIRROR" \
       AGENT_CLI_SET="$AGENT_CLI_SET" \
       /tmp/install-agent-runtime.sh \
    && rm -f /tmp/install-agent-runtime.sh

WORKDIR /workspace
