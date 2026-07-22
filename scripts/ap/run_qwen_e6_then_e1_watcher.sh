#!/usr/bin/env bash
set -uo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench"
readonly PRIVATE_ENV="/cpfs01/user/zhangfengji.zfj/workspace/.env"
readonly STATE_DIR="/cpfs02/user/zhangfengji.zfj/skillevolbench_stability_20260722/watch-qwen-e6-then-e1"

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

# shellcheck disable=SC1090
source "${PRIVATE_ENV}"
export AP_API_KEY="${AP_KEY:?AP_KEY is required}"
export AP_CLUSTER="hk-benchmark-dev"
export MODEL_API_KEY="${DASHSCOPE_API_KEY:?DASHSCOPE_API_KEY is required}"
export MODEL_BASE_URL="${DASHSCOPE_API_URL:?DASHSCOPE_API_URL is required}"
export MODEL_NAME="${QWEN37_MODEL_NAME:?QWEN37_MODEL_NAME is required}"

while [[ ! -f "${STATE_DIR}/completed.json" ]]; do
  python "${REPO_ROOT}/scripts/ap/watch_qwen_e6_then_e1.py" \
    --repo-root "${REPO_ROOT}" \
    --state-dir "${STATE_DIR}"
  exit_code=$?
  if [[ -f "${STATE_DIR}/completed.json" ]]; then
    break
  fi
  printf '%s watcher exited with code %s; restarting in 15 seconds\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${exit_code}"
  sleep 15
done

printf '%s watcher supervisor completed\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
