#!/usr/bin/env bash
set -euo pipefail
set +x
umask 077

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench-v1.1"
readonly AUDIT_ROOT="/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_v1_1_19_20260802"
readonly CONTROLLER_SESSION="sevb-v19-matrix-controller"
readonly EXPORT_SESSION="sevb-v19-export-watcher"
readonly POLL_SECONDS=60
readonly STALE_SECONDS=300

mkdir -p "$AUDIT_ROOT/guardian"
exec 9>"$AUDIT_ROOT/guardian/guardian.lock"
flock -n 9 || exit 75

healthy() {
  local session="$1"
  local heartbeat="$2"
  tmux has-session -t "$session" 2>/dev/null || return 1
  [[ "$(tmux list-panes -t "$session" -F '#{pane_dead}' | sort -u)" == "0" ]] \
    || return 1
  [[ -f "$heartbeat" ]] || return 1
  local modified
  modified="$(stat -c '%Y' "$heartbeat")" || return 1
  (( $(date +%s) - modified <= STALE_SECONDS ))
}

restart() {
  local session="$1"
  local runner="$2"
  local heartbeat="$3"
  tmux kill-session -t "$session" 2>/dev/null || true
  tmux new-session -d -s "$session" "bash $runner"
  sleep 2
  healthy "$session" "$heartbeat"
}

while true; do
  controller_heartbeat="$AUDIT_ROOT/matrix-controller/heartbeat.json"
  export_heartbeat="$AUDIT_ROOT/watcher/heartbeat.json"
  if [[ -f "$AUDIT_ROOT/matrix-controller/completed.json" ]]; then
    controller_status="completed"
  elif healthy "$CONTROLLER_SESSION" "$controller_heartbeat"; then
    controller_status="healthy"
  elif restart \
      "$CONTROLLER_SESSION" \
      "$REPO_ROOT/experiments/full_180_quality_audit/run_v19_matrix_controller.sh" \
      "$controller_heartbeat"; then
    controller_status="restarted"
  else
    controller_status="restart_failed"
  fi

  if healthy "$EXPORT_SESSION" "$export_heartbeat"; then
    export_status="healthy"
  elif restart \
      "$EXPORT_SESSION" \
      "$REPO_ROOT/experiments/full_180_quality_audit/run_v19_export_watcher.sh" \
      "$export_heartbeat"; then
    export_status="restarted"
  else
    export_status="restart_failed"
  fi

  temporary="$AUDIT_ROOT/guardian/.heartbeat.json.$$"
  printf '{"updated_at_utc":"%s","controller":"%s","export_watcher":"%s"}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$controller_status" "$export_status" \
    > "$temporary"
  chmod 600 "$temporary"
  mv -f "$temporary" "$AUDIT_ROOT/guardian/heartbeat.json"
  sleep "$POLL_SECONDS"
done
