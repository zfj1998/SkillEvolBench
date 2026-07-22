#!/usr/bin/env bash
set -uo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench"
readonly PRIVATE_ENV="/cpfs01/user/zhangfengji.zfj/workspace/.env"
readonly STATE_DIR="/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723/watcher"
readonly LOG_PATH="${STATE_DIR}/supervisor.log"

mkdir -p "${STATE_DIR}"
chmod 700 "${STATE_DIR}"

# shellcheck disable=SC1090
source "${PRIVATE_ENV}"
export AP_API_KEY="${AP_KEY:?AP_KEY is required}"
export AP_CLUSTER="hk-benchmark-dev"

# The supervisor deliberately never exits on an idle study. The manifest can
# receive new oracle jobs after the initial self-generated runs are complete.
while true; do
  python "${REPO_ROOT}/scripts/ap/watch_t56_oracle_study.py" \
    --repo-root "${REPO_ROOT}" \
    --state-dir "${STATE_DIR}" \
    --evidence-dir "${STATE_DIR%/watcher}/raw"
  exit_code=$?
  printf '%s watcher exited with code %s; restarting in 15 seconds\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${exit_code}" >>"${LOG_PATH}"
  sleep 15
done
