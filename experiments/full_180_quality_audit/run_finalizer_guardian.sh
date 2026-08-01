#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly RUNNER="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1/experiments/full_180_quality_audit/run_finalizer.sh"
readonly STATE_DIR="/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_20260802/finalizer"
readonly SESSION="sevb-full-180-finalizer"
readonly POLL_SECONDS=60
readonly STALE_SECONDS=360

mkdir -p "$STATE_DIR/guardian"
exec 9>"$STATE_DIR/guardian/guardian.lock"
flock -n 9 || exit 75

healthy() {
  tmux has-session -t "$SESSION" 2>/dev/null || return 1
  [[ "$(tmux list-panes -t "$SESSION" -F '#{pane_dead}' | sort -u)" == "0" ]] \
    || return 1
  [[ -f "$STATE_DIR/heartbeat.json" ]] || return 1
  local modified
  modified="$(stat -c '%Y' "$STATE_DIR/heartbeat.json")" || return 1
  (( $(date +%s) - modified <= STALE_SECONDS ))
}

restart() {
  tmux kill-session -t "$SESSION" 2>/dev/null || true
  tmux new-session -d -s "$SESSION" "bash $RUNNER"
  sleep 2
  healthy
}

while true; do
  if [[ -f "$STATE_DIR/completed.json" ]]; then
    exit 0
  fi
  if healthy; then
    status="healthy"
  elif restart; then
    status="restarted"
  else
    status="restart_failed"
  fi
  temporary="$STATE_DIR/guardian/.heartbeat.json.$$"
  printf '{"updated_at_utc":"%s","status":"%s","session":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$status" "$SESSION" > "$temporary"
  chmod 600 "$temporary"
  mv -f "$temporary" "$STATE_DIR/guardian/heartbeat.json"
  sleep "$POLL_SECONDS"
done
