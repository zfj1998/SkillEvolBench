#!/usr/bin/env bash
set -uo pipefail
set +x
umask 077

# Keep both long-lived T5/T6 study watchers alive.  The child watchers own all
# AP submission/export idempotency; this guardian only recreates stale or dead
# tmux supervisors and therefore cannot submit a duplicate group by itself.

readonly REPO_ROOT="/cpfs01/user/zhangfengji.zfj/workspace/SkillEvolBench"
readonly STUDY_ROOT="/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723"
readonly GUARDIAN_DIR="${STUDY_ROOT}/guardian"
readonly HEARTBEAT_PATH="${GUARDIAN_DIR}/heartbeat.json"
readonly LOG_PATH="${GUARDIAN_DIR}/guardian.log"
readonly POLL_SECONDS=60
readonly STALE_SECONDS=420

mkdir -p "${GUARDIAN_DIR}"
chmod 700 "${GUARDIAN_DIR}"

exec 9>"${GUARDIAN_DIR}/guardian.lock"
if ! flock -n 9; then
  exit 75
fi

session_name() {
  case "$1" in
    matrix) printf '%s' "sevb-t56-oracle-matrix-watch" ;;
    evidence) printf '%s' "sevb-t56-oracle-study-watch" ;;
    *) return 2 ;;
  esac
}

runner_path() {
  case "$1" in
    matrix) printf '%s' "${REPO_ROOT}/scripts/ap/run_t56_oracle_matrix_watcher.sh" ;;
    evidence) printf '%s' "${REPO_ROOT}/scripts/ap/run_t56_oracle_study_watcher.sh" ;;
    *) return 2 ;;
  esac
}

watcher_heartbeat() {
  case "$1" in
    matrix) printf '%s' "${STUDY_ROOT}/matrix-watcher/heartbeat.json" ;;
    evidence) printf '%s' "${STUDY_ROOT}/watcher/heartbeat.json" ;;
    *) return 2 ;;
  esac
}

supervisor_log() {
  case "$1" in
    matrix) printf '%s' "${STUDY_ROOT}/matrix-watcher/supervisor.log" ;;
    evidence) printf '%s' "${STUDY_ROOT}/watcher/supervisor.log" ;;
    *) return 2 ;;
  esac
}

is_healthy() {
  local kind="$1"
  local session heartbeat heartbeat_mtime
  session="$(session_name "${kind}")" || return 1
  heartbeat="$(watcher_heartbeat "${kind}")" || return 1

  tmux has-session -t "${session}" 2>/dev/null || return 1
  [[ "$(tmux list-panes -t "${session}" -F '#{pane_dead}' 2>/dev/null | sort -u)" == "0" ]] || return 1
  [[ -f "${heartbeat}" ]] || return 1
  heartbeat_mtime="$(stat -c '%Y' "${heartbeat}" 2>/dev/null)" || return 1
  (( $(date +%s) - heartbeat_mtime <= STALE_SECONDS ))
}

restart_watcher() {
  local kind="$1"
  local session runner log_path
  session="$(session_name "${kind}")" || return 1
  runner="$(runner_path "${kind}")" || return 1
  log_path="$(supervisor_log "${kind}")" || return 1

  tmux kill-session -t "${session}" 2>/dev/null || true
  tmux new-session -d -s "${session}" \
    "bash ${runner} >>${log_path} 2>&1"
  sleep 2
  is_healthy "${kind}"
}

write_heartbeat() {
  local matrix_state="$1"
  local evidence_state="$2"
  local temporary="${HEARTBEAT_PATH}.$$"
  printf '{\n  "updated_at_utc": "%s",\n  "guardian_status": "%s",\n  "matrix_watcher": "%s",\n  "evidence_watcher": "%s",\n  "next_check_seconds": %s\n}\n' \
    "$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
    "$([[ "${matrix_state}" == "healthy" && "${evidence_state}" == "healthy" ]] && printf healthy || printf degraded)" \
    "${matrix_state}" \
    "${evidence_state}" \
    "${POLL_SECONDS}" >"${temporary}"
  chmod 600 "${temporary}"
  mv -f "${temporary}" "${HEARTBEAT_PATH}"
}

printf '%s study guardian started pid=%s\n' \
  "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$$" >>"${LOG_PATH}"

while true; do
  matrix_state="healthy"
  evidence_state="healthy"

  if ! is_healthy matrix; then
    if restart_watcher matrix; then
      printf '%s restarted matrix watcher\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
    else
      matrix_state="restart_failed"
      printf '%s failed to restart matrix watcher\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
    fi
  fi

  if ! is_healthy evidence; then
    if restart_watcher evidence; then
      printf '%s restarted evidence watcher\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
    else
      evidence_state="restart_failed"
      printf '%s failed to restart evidence watcher\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >>"${LOG_PATH}"
    fi
  fi

  write_heartbeat "${matrix_state}" "${evidence_state}"
  sleep "${POLL_SECONDS}"
done
