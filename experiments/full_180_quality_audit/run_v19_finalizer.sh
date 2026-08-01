#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1"
readonly AUDIT_ROOT="/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_v1_1_19_20260802"

exec python \
  "$REPO_ROOT/experiments/full_180_quality_audit/finalize_v19_when_ready.py" \
  --repo-root "$REPO_ROOT" \
  --audit-root "$AUDIT_ROOT" \
  --poll-sec 120
