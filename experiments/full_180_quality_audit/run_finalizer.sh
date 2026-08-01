#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1"

exec python \
  "$REPO_ROOT/experiments/full_180_quality_audit/finalize_when_ready.py" \
  --repo-root "$REPO_ROOT" \
  --poll-sec 120
