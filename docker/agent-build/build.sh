#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

: "${CONTAINER_BUILDER:=docker}"
: "${CONTAINER_BUILDER_ARGS:=}"
: "${CONTAINER_BUILD_ARGS:=}"
: "${IMAGE_NAME:=agent-runtime}"
: "${IMAGE_TAG:=latest}"
: "${NODE_VERSION:=22}"
: "${NVM_VERSION:=v0.40.2}"
: "${CLAUDE_CODE_VERSION:=latest}"
: "${GEMINI_CLI_VERSION:=latest}"
: "${CODEX_CLI_VERSION:=latest}"
: "${KIMI_CLI_VERSION:=latest}"
: "${OPENCLAW_VERSION:=latest}"

sanitize_tag_part() {
  printf '%s' "$1" | tr '/:@+' '----' | tr -cd '[:alnum:]_.-'
}

read -r -a CONTAINER_BUILDER_ARGS_ARRAY <<< "$CONTAINER_BUILDER_ARGS"
read -r -a CONTAINER_BUILD_ARGS_ARRAY <<< "$CONTAINER_BUILD_ARGS"

"$CONTAINER_BUILDER" "${CONTAINER_BUILDER_ARGS_ARRAY[@]}" build \
  "${CONTAINER_BUILD_ARGS_ARRAY[@]}" \
  --build-arg "NODE_VERSION=$NODE_VERSION" \
  --build-arg "NVM_VERSION=$NVM_VERSION" \
  --build-arg "CLAUDE_CODE_VERSION=$CLAUDE_CODE_VERSION" \
  --build-arg "GEMINI_CLI_VERSION=$GEMINI_CLI_VERSION" \
  --build-arg "CODEX_CLI_VERSION=$CODEX_CLI_VERSION" \
  --build-arg "KIMI_CLI_VERSION=$KIMI_CLI_VERSION" \
  --build-arg "OPENCLAW_VERSION=$OPENCLAW_VERSION" \
  -f "$SCRIPT_DIR/Dockerfile" \
  -t "$IMAGE_NAME:$IMAGE_TAG" \
  "$SCRIPT_DIR"

VERSION_TAG="node-$(sanitize_tag_part "$NODE_VERSION")"
VERSION_TAG="$VERSION_TAG-claude-$(sanitize_tag_part "$CLAUDE_CODE_VERSION")"
VERSION_TAG="$VERSION_TAG-gemini-$(sanitize_tag_part "$GEMINI_CLI_VERSION")"
VERSION_TAG="$VERSION_TAG-codex-$(sanitize_tag_part "$CODEX_CLI_VERSION")"
VERSION_TAG="$VERSION_TAG-kimi-$(sanitize_tag_part "$KIMI_CLI_VERSION")"
VERSION_TAG="$VERSION_TAG-openclaw-$(sanitize_tag_part "$OPENCLAW_VERSION")"

"$CONTAINER_BUILDER" "${CONTAINER_BUILDER_ARGS_ARRAY[@]}" tag "$IMAGE_NAME:$IMAGE_TAG" "$IMAGE_NAME:$VERSION_TAG"

echo "Built $IMAGE_NAME:$IMAGE_TAG"
echo "Tagged $IMAGE_NAME:$VERSION_TAG"
