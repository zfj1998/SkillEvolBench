#!/usr/bin/env bash
set -uo pipefail
set +x
umask 077

# Keep the Qwen E6 -> E1 watcher alive even if its tmux session disappears.
# The inner watcher owns all AP state and idempotency.  This guardian only
# recreates the tmux supervisor; it never submits an AP job itself.

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench"
readonly RUNNER="${REPO_ROOT}/scripts/ap/run_qwen_e6_then_e1_watcher.sh"
readonly STATE_DIR="/cpfs02/user/zhangfengji.zfj/skillevolbench_stability_20260722/watch-qwen-e6-then-e1"
readonly GUARDIAN_DIR="${STATE_DIR}/guardian"
readonly SESSION="sevb-qwen-e6-then-e1-watch"
readonly LOG_PATH="${GUARDIAN_DIR}/guardian.log"
readonly HEARTBEAT_PATH="${GUARDIAN_DIR}/heartbeat.json"
readonly POLL_SECONDS=60

mkdir -p "${GUARDIAN_DIR}"
chmod 700 "${GUARDIAN_DIR}"

exec 9>"${GUARDIAN_DIR}/guardian.lock"
if ! flock -n 9; then
  printf '%s guardian is already running\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
  exit 75
fi

write_heartbeat() {
  local status="$1"
  local session_state="$2"
  local next_action="$3"
  local temporary="${HEARTBEAT_PATH}.$$"
  printf '{\n  "updated_at_utc": "%s",\n  "guardian_status": "%s",\n  "tmux_session": "%s",\n  "session_state": "%s",\n  "next_action": "%s"\n}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "${status}" \
    "${SESSION}" \
    "${session_state}" \
    "${next_action}" >"${temporary}"
  chmod 600 "${temporary}"
  mv -f "${temporary}" "${HEARTBEAT_PATH}"
}

session_is_healthy() {
  tmux has-session -t "${SESSION}" 2>/dev/null || return 1
  [[ "$(tmux list-panes -t "${SESSION}" -F '#{pane_dead}' 2>/dev/null | sort -u)" == "0" ]]
}

start_session() {
  tmux kill-session -t "${SESSION}" 2>/dev/null || true
  tmux new-session -d -s "${SESSION}" \
    "bash ${RUNNER} >>${STATE_DIR}/supervisor.log 2>&1"
  sleep 2
  session_is_healthy
}

printf '%s guardian started pid=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" >>"${LOG_PATH}"

while true; do
  if [[ -f "${STATE_DIR}/completed.json" ]]; then
    write_heartbeat "completed" "not_required" "none"
    printf '%s E1 watcher completed; guardian exiting\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
    exit 0
  fi

  if session_is_healthy; then
    write_heartbeat "active" "healthy" "check again in ${POLL_SECONDS} seconds"
  elif start_session; then
    write_heartbeat "active" "restarted" "check again in ${POLL_SECONDS} seconds"
    printf '%s restarted tmux session %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SESSION}" >>"${LOG_PATH}"
  else
    write_heartbeat "degraded" "restart_failed" "retry in ${POLL_SECONDS} seconds"
    printf '%s failed to restart tmux session %s\n' \
      "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "${SESSION}" >>"${LOG_PATH}"
  fi

  sleep "${POLL_SECONDS}"
done
