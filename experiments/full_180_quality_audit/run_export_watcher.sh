#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1"
readonly PRIVATE_ENV="/cpfs01/user/zhangfengji.zfj/workspace/.env"
readonly AUDIT_ROOT="/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_20260802"

set -a
# shellcheck disable=SC1090
source "$PRIVATE_ENV"
set +a
export AP_API_KEY="${AP_KEY:?AP_KEY is required}"
export AP_CLUSTER="hk-benchmark-dev"
unset AP_HEADERS

exec python "$REPO_ROOT/scripts/ap/watch_t56_oracle_study.py" \
  --repo-root "$REPO_ROOT" \
  --state-dir "$AUDIT_ROOT/watcher" \
  --evidence-dir "$AUDIT_ROOT/raw" \
  --cluster "$AP_CLUSTER" \
  --poll-sec 60 \
  --no-analysis
