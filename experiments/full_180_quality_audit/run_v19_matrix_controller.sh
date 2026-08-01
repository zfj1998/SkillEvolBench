#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1"
readonly PRIVATE_ENV="/cpfs01/user/zhangfengji.zfj/workspace/.env"
readonly AUDIT_ROOT="/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_v1_1_19_20260802"

set -a
# shellcheck disable=SC1090
source "$PRIVATE_ENV"
set +a
export AP_API_KEY="${AP_KEY:?AP_KEY is required}"
export AP_CLUSTER="hk-benchmark-dev"
unset AP_HEADERS
export MODEL_API_KEY="${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is required}"
export MODEL_BASE_URL="${DASHSCOPE_API_URL:?DASHSCOPE_API_URL is required}"
export MODEL_NAME="${QWEN37_MODEL_NAME:?QWEN37_MODEL_NAME is required}"

exec python \
  "$REPO_ROOT/experiments/full_180_quality_audit/watch_v19_matrix.py" \
  --repo-root "$REPO_ROOT" \
  --audit-root "$AUDIT_ROOT" \
  --cluster "$AP_CLUSTER" \
  --poll-sec 60
