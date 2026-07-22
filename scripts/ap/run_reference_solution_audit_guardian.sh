#!/usr/bin/env bash
set -uo pipefail
set +x
umask 077

readonly RUNNER="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench/scripts/ap/run_reference_solution_audit_watcher.sh"
readonly STATE_DIR="/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723/reference-audit-watcher"
readonly GUARDIAN_DIR="${STATE_DIR}/guardian"
readonly SESSION="sevb-reference-solution-audit-watch"
readonly POLL_SECONDS=60

mkdir -p "${GUARDIAN_DIR}"
chmod 700 "${GUARDIAN_DIR}"
exec 9>"${GUARDIAN_DIR}/guardian.lock"
flock -n 9 || exit 75

write_heartbeat() {
  local status="$1"
  local session_state="$2"
  local temporary="${GUARDIAN_DIR}/heartbeat.json.$$"
  printf '{\n  "updated_at_utc": "%s",\n  "status": "%s",\n  "tmux_session": "%s",\n  "session_state": "%s",\n  "next_poll_seconds": %s\n}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${status}" \
    "${SESSION}" \
    "${session_state}" \
    "${POLL_SECONDS}" >"${temporary}"
  chmod 600 "${temporary}"
  mv -f "${temporary}" "${GUARDIAN_DIR}/heartbeat.json"
}

session_is_healthy() {
  tmux has-session -t "${SESSION}" 2>/dev/null || return 1
  [[ "$(tmux list-panes -t "${SESSION}" -F '#{pane_dead}' 2>/dev/null | sort -u)" == "0" ]]
}

restart_session() {
  tmux kill-session -t "${SESSION}" 2>/dev/null || true
  tmux new-session -d -s "${SESSION}" "bash ${RUNNER}"
  sleep 2
  session_is_healthy
}

while true; do
  if [[ -f "${STATE_DIR}/completed.json" ]]; then
    write_heartbeat "completed" "not_required"
    exit 0
  fi
  if session_is_healthy; then
    write_heartbeat "active" "healthy"
  elif restart_session; then
    write_heartbeat "active" "restarted"
    printf '%s restarted %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SESSION}" \
      >>"${GUARDIAN_DIR}/guardian.log"
  else
    write_heartbeat "degraded" "restart_failed"
  fi
  sleep "${POLL_SECONDS}"
done
