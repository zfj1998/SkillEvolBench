#!/usr/bin/env python3
"""Serialize the Qwen E6 repair and a follow-up E1 repair on AP.

This is an operational watcher, not benchmark protocol logic.  It keeps API
credentials in the process environment, writes only credential-free state, and
uses one persisted idempotency key so a submission transport failure cannot
create duplicate E1 jobs.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


E6_JOB_ID = "ap-skillevolbench-db6d3f92d0444481-d2"
OLD_E1_CREATED_AT = "2026-07-22T19:24:05.200"
AGENTHUB_REF = "a32ea0ecd2daf6661dd3212d973d0f8e222f3a77"
TERMINAL_STATUSES = {"Succeeded", "Failed", "Cancelled"}
ACTIVE_STATUSES = {"Queued", "Pending", "Running"}
MAX_E1_REPAIR_JOBS = 3
DEFAULT_STATE_DIR = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_stability_20260722/"
    "watch-qwen-e6-then-e1"
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(content, encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


class WatcherError(RuntimeError):
    pass


class Watcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.state_dir = args.state_dir.resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        self.secrets = [
            self.environment.get(name, "")
            for name in ("AP_API_KEY", "MODEL_API_KEY")
            if self.environment.get(name, "")
        ]
        missing = [
            name
            for name in (
                "AP_API_KEY",
                "MODEL_API_KEY",
                "MODEL_BASE_URL",
                "MODEL_NAME",
            )
            if not self.environment.get(name)
        ]
        if missing:
            raise WatcherError(
                "required environment variables are missing: " + ", ".join(missing)
            )
        self.control_path = self.state_dir / "control.json"
        self.control: dict[str, Any] = read_json(self.control_path, {})

    def redact(self, text: str) -> str:
        result = text
        for secret in self.secrets:
            if len(secret) >= 6:
                result = result.replace(secret, "[REDACTED]")
        return result

    def event(self, event: str, **fields: Any) -> None:
        record = {"timestamp_utc": utc_now(), "event": event, **fields}
        line = self.redact(
            json.dumps(record, ensure_ascii=False, separators=(",", ":"))
        )
        path = self.state_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        os.chmod(path, 0o600)

    def heartbeat(
        self,
        phase: str,
        *,
        e6_status: str | None = None,
        e1_job_id: str | None = None,
        e1_status: str | None = None,
        next_action: str,
        error: str | None = None,
    ) -> None:
        payload: dict[str, Any] = {
            "updated_at_utc": utc_now(),
            "watcher_status": "active",
            "watcher_phase": phase,
            "e6_job_id": E6_JOB_ID,
            "e6_status": e6_status,
            "e1_job_id": e1_job_id,
            "e1_status": e1_status,
            "next_action": next_action,
        }
        if error:
            payload["last_error"] = self.redact(error)[:1000]
        write_json(self.state_dir / "heartbeat.json", payload)
        status_lines = [f"{key}: {value}" for key, value in payload.items()]
        atomic_write(self.state_dir / "status.txt", "\n".join(status_lines) + "\n")

    def save_control(self) -> None:
        write_json(self.control_path, self.control)

    def run_ap(self, arguments: list[str], *, timeout: int = 90) -> str:
        try:
            result = subprocess.run(
                [self.args.ap_cli, *arguments],
                cwd=self.args.repo_root,
                env=self.environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=timeout,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WatcherError(f"AP CLI timed out after {timeout}s") from exc
        if result.returncode != 0:
            diagnostic = self.redact(result.stderr.strip() or result.stdout.strip())
            raise WatcherError(
                f"AP CLI failed with exit {result.returncode}: {diagnostic[-1000:]}"
            )
        return result.stdout

    def get_job(self, job_id: str) -> dict[str, Any]:
        output = self.run_ap(["job", "get", job_id])
        try:
            value = json.loads(output)
        except json.JSONDecodeError as exc:
            raise WatcherError(f"invalid job JSON for {job_id}") from exc
        if not isinstance(value, dict) or value.get("job_id") != job_id:
            raise WatcherError(f"unexpected job response for {job_id}")
        return value

    def list_jobs(
        self, instance_id: str, *, active_only: bool = False
    ) -> list[dict[str, Any]]:
        arguments = [
            "job",
            "list",
            "--template",
            "skillevolbench",
            "--instance-id",
            instance_id,
            "--sort",
            "created_at",
            "--desc",
            "--limit",
            "100",
            "--format",
            "json",
        ]
        if active_only:
            arguments.append("--active-only")
        output = self.run_ap(arguments)
        try:
            value = json.loads(output)
            jobs = value["jobs"]
        except (json.JSONDecodeError, KeyError, TypeError) as exc:
            raise WatcherError(f"invalid AP job-list JSON for {instance_id}") from exc
        if not isinstance(jobs, list):
            raise WatcherError(f"AP job-list jobs is not a list for {instance_id}")
        return [job for job in jobs if isinstance(job, dict)]

    @staticmethod
    def is_qwen_repair(job: dict[str, Any]) -> bool:
        return (
            job.get("agenthub_revision") == AGENTHUB_REF and job.get("group_id") is None
        )

    def find_existing_e1(self) -> dict[str, Any] | None:
        failed_job_ids = {
            str(item.get("job_id"))
            for item in self.control.get("failed_e1_jobs", [])
            if isinstance(item, dict) and item.get("job_id")
        }
        for job in self.list_jobs("E1"):
            created_at = str(job.get("created_at") or "")
            if (
                self.is_qwen_repair(job)
                and created_at > OLD_E1_CREATED_AT
                and job.get("job_id")
                and job.get("job_id") not in failed_job_ids
                and job.get("status") in {*ACTIVE_STATUSES, "Succeeded"}
            ):
                return job
        return None

    def find_conflicting_active_repair(self) -> dict[str, Any] | None:
        for instance_id in ("E1", "E6"):
            for job in self.list_jobs(instance_id, active_only=True):
                if not self.is_qwen_repair(job):
                    continue
                if job.get("job_id") == E6_JOB_ID:
                    continue
                if job.get("status") in ACTIVE_STATUSES:
                    return job
        return None

    def idempotency_key(self) -> str:
        path = self.state_dir / "idempotency_key.txt"
        try:
            value = path.read_text(encoding="utf-8").strip()
            uuid.UUID(value)
            return value
        except (FileNotFoundError, OSError, ValueError):
            value = str(uuid.uuid4())
            atomic_write(path, value + "\n")
            return value

    def rotate_idempotency_key(self) -> None:
        try:
            (self.state_dir / "idempotency_key.txt").unlink()
        except FileNotFoundError:
            pass

    def submit_command(self, *, dry_run: bool) -> list[str]:
        command = [
            sys.executable,
            str(self.args.repo_root / "scripts/ap/submit.py"),
            "--scope",
            "environment",
            "--environment-id",
            "E1",
            "--cluster",
            self.args.cluster,
            "--agenthub-ref",
            AGENTHUB_REF,
            "--dataset",
            "skillevolbench/skillevolbench",
            "--split",
            "v1@15",
            "--model",
            "qwen3.7-max",
            "--model-base-url",
            self.environment["MODEL_BASE_URL"],
            "--harbor-agent",
            "opencode",
            "--model-provider",
            "dashscope",
            "--model-api-protocol",
            "openai",
            "--learning-max-attempts",
            "3",
            "--harbor-agent-timeout-multiplier",
            "6",
            "--runtime-timeout-sec",
            "172800",
            "--episode-retry-max-attempts",
            "2",
            "--episode-retry-backoff-sec",
            "300",
            "--concurrency",
            "1",
            "--probe-mode",
            "chat",
            "--idempotency-key",
            self.idempotency_key(),
        ]
        if dry_run:
            command.append("--dry-run")
        return command

    def run_submit(self, *, dry_run: bool) -> str:
        try:
            result = subprocess.run(
                self.submit_command(dry_run=dry_run),
                cwd=self.args.repo_root,
                env=self.environment,
                text=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                timeout=180,
                check=False,
            )
        except subprocess.TimeoutExpired as exc:
            raise WatcherError(
                "submission command timed out; idempotency key retained"
            ) from exc
        combined = self.redact(result.stdout + result.stderr)
        log_name = "dry_run.log" if dry_run else "submission.raw.log"
        atomic_write(self.state_dir / log_name, combined)
        if result.returncode != 0:
            raise WatcherError(
                f"{'dry-run' if dry_run else 'submission'} failed with exit "
                f"{result.returncode}: {combined[-1000:]}"
            )
        return result.stdout

    @staticmethod
    def parse_submission(output: str) -> dict[str, Any]:
        decoder = json.JSONDecoder()
        for index, character in enumerate(output):
            if character != "{":
                continue
            try:
                value, _ = decoder.raw_decode(output[index:])
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and isinstance(value.get("submission"), dict):
                return value
        raise WatcherError("submission output did not contain a submission object")

    def record_e1(self, job: dict[str, Any], source: str) -> str:
        job_id = str(job.get("job_id") or "")
        if not job_id:
            raise WatcherError("E1 job record is missing job_id")
        payload = {
            "recorded_at_utc": utc_now(),
            "source": source,
            "job_id": job_id,
            "status": job.get("status"),
            "instance_id": job.get("instance_id"),
            "agenthub_revision": job.get("agenthub_revision"),
            "idempotency_key": self.idempotency_key(),
            "console_url": (
                "https://agentplatform.aliyun-inc.com/?cluster="
                f"{self.args.cluster}#/jobs/{job_id}"
            ),
        }
        write_json(self.state_dir / "submission.json", payload)
        self.event("e1_recorded", **payload)
        return job_id

    def submitted_e1_job_id(self) -> str | None:
        value = read_json(self.state_dir / "submission.json", {})
        job_id = value.get("job_id") if isinstance(value, dict) else None
        return str(job_id) if job_id else None

    def monitor_e1(self, job_id: str) -> bool:
        job = self.get_job(job_id)
        status = str(job.get("status") or "Unknown")
        if status == "Succeeded":
            completed = {
                "completed_at_utc": utc_now(),
                "watcher_status": "completed",
                "e6_job_id": E6_JOB_ID,
                "e1_job_id": job_id,
                "e1_status": status,
                "console_url": (
                    "https://agentplatform.aliyun-inc.com/?cluster="
                    f"{self.args.cluster}#/jobs/{job_id}"
                ),
            }
            write_json(self.state_dir / "completed.json", completed)
            self.heartbeat(
                "completed",
                e1_job_id=job_id,
                e1_status=status,
                next_action="none",
            )
            self.event("watcher_completed", **completed)
            return True
        if status in {"Failed", "Cancelled"}:
            return self.handle_unsuccessful_e1(job_id, status)
        self.heartbeat(
            "monitoring_e1",
            e1_job_id=job_id,
            e1_status=status,
            next_action=f"poll E1 again in {self.args.poll_sec} seconds",
        )
        return False

    def handle_unsuccessful_e1(self, job_id: str, status: str) -> bool:
        failures = self.control.setdefault("failed_e1_jobs", [])
        if not isinstance(failures, list):
            failures = []
            self.control["failed_e1_jobs"] = failures
        known_ids = {
            str(item.get("job_id"))
            for item in failures
            if isinstance(item, dict) and item.get("job_id")
        }
        if job_id not in known_ids:
            failures.append(
                {
                    "job_id": job_id,
                    "status": status,
                    "observed_at_utc": utc_now(),
                }
            )

        if status == "Cancelled" or len(failures) >= MAX_E1_REPAIR_JOBS:
            self.control["repair_exhausted"] = True
            self.control["repair_exhausted_at_utc"] = utc_now()
            self.save_control()
            self.heartbeat(
                "repair_exhausted",
                e1_job_id=job_id,
                e1_status=status,
                next_action="manual review required; watcher remains active",
            )
            self.event(
                "e1_repair_exhausted",
                e1_job_id=job_id,
                e1_status=status,
                failed_repair_jobs=len(failures),
            )
            return False

        self.control["next_submit_attempt_epoch"] = time.time() + 300
        self.control["last_failed_e1_job_id"] = job_id
        self.control["last_failed_e1_status"] = status
        self.save_control()
        try:
            (self.state_dir / "submission.json").unlink()
        except FileNotFoundError:
            pass
        self.rotate_idempotency_key()
        self.heartbeat(
            "e1_repair_backoff",
            e1_job_id=job_id,
            e1_status=status,
            next_action="submit a fresh E1 repair in 300 seconds",
        )
        self.event(
            "e1_repair_retry_scheduled",
            e1_job_id=job_id,
            e1_status=status,
            next_repair_number=len(failures) + 1,
        )
        return False

    def step(self) -> bool:
        if self.control.get("repair_exhausted") is True:
            failures = self.control.get("failed_e1_jobs", [])
            last = failures[-1] if isinstance(failures, list) and failures else {}
            self.heartbeat(
                "repair_exhausted",
                e1_job_id=str(last.get("job_id") or "") or None,
                e1_status=str(last.get("status") or "") or None,
                next_action="manual review required; watcher remains active",
            )
            return False
        existing_job_id = self.submitted_e1_job_id()
        if existing_job_id:
            return self.monitor_e1(existing_job_id)

        e6 = self.get_job(E6_JOB_ID)
        e6_status = str(e6.get("status") or "Unknown")
        if e6_status not in TERMINAL_STATUSES:
            self.heartbeat(
                "waiting_for_e6_terminal",
                e6_status=e6_status,
                next_action=f"poll E6 again in {self.args.poll_sec} seconds",
            )
            return False

        terminal_epoch = self.control.get("e6_terminal_observed_epoch")
        if not isinstance(terminal_epoch, (int, float)):
            terminal_epoch = time.time()
            self.control["e6_terminal_observed_epoch"] = terminal_epoch
            self.control["e6_terminal_observed_at_utc"] = utc_now()
            self.control["e6_terminal_status"] = e6_status
            self.save_control()
            self.event("e6_terminal_observed", e6_status=e6_status)

        remaining = max(0, int(self.args.quiet_sec - (time.time() - terminal_epoch)))
        if remaining > 0:
            self.heartbeat(
                "quiet_period",
                e6_status=e6_status,
                next_action=f"wait {remaining} more seconds before E1 preflight",
            )
            return False

        existing = self.find_existing_e1()
        if existing is not None:
            job_id = self.record_e1(existing, "adopted-existing")
            return self.monitor_e1(job_id)

        conflict = self.find_conflicting_active_repair()
        if conflict is not None:
            self.heartbeat(
                "blocked_by_active_repair",
                e6_status=e6_status,
                next_action=f"wait for active repair {conflict.get('job_id')}",
            )
            return False

        if self.args.observe_only:
            self.heartbeat(
                "observe_only_ready",
                e6_status=e6_status,
                next_action="submission disabled by --observe-only",
            )
            return False

        next_attempt = self.control.get("next_submit_attempt_epoch", 0)
        if isinstance(next_attempt, (int, float)) and time.time() < next_attempt:
            remaining = int(next_attempt - time.time())
            self.heartbeat(
                "preflight_backoff",
                e6_status=e6_status,
                next_action=f"retry preflight in {remaining} seconds",
            )
            return False

        try:
            self.run_submit(dry_run=True)
            self.event("e1_dry_run_passed", e6_status=e6_status)
            raw_output = self.run_submit(dry_run=False)
            submission = self.parse_submission(raw_output)
            jobs = submission["submission"].get("jobs", [])
            if len(jobs) != 1 or jobs[0].get("instance_id") != "E1":
                raise WatcherError("submission did not return exactly one E1 job")
            job_id = self.record_e1(jobs[0], "submitted")
            return self.monitor_e1(job_id)
        except WatcherError:
            self.control["next_submit_attempt_epoch"] = time.time() + 300
            self.control["last_submit_error_at_utc"] = utc_now()
            self.save_control()
            raise

    def run(self) -> int:
        while True:
            try:
                completed = self.step()
                if completed:
                    return 0
            except WatcherError as exc:
                diagnostic = self.redact(str(exc))[:1000]
                self.event("transient_error", diagnostic=diagnostic)
                self.heartbeat(
                    "transient_error",
                    next_action=f"retry in {self.args.error_backoff_sec} seconds",
                    error=diagnostic,
                )
                if self.args.once:
                    return 1
                time.sleep(self.args.error_backoff_sec)
                continue
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--cluster", default="hk-benchmark-dev")
    parser.add_argument("--ap-cli", default="ap")
    parser.add_argument("--poll-sec", type=int, default=45)
    parser.add_argument("--error-backoff-sec", type=int, default=60)
    parser.add_argument("--quiet-sec", type=int, default=900)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--observe-only",
        action="store_true",
        help="monitor and write state, but never submit E1",
    )
    args = parser.parse_args()
    if args.poll_sec < 5 or args.error_backoff_sec < 5 or args.quiet_sec < 0:
        parser.error("poll/backoff must be >=5 seconds and quiet period must be >=0")
    return args


def main() -> int:
    args = parse_args()
    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = args.state_dir / "watcher.lock"
    lock_handle = lock_path.open("a+", encoding="utf-8")
    os.chmod(lock_path, 0o600)
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("watcher already running", file=sys.stderr)
        return 75
    try:
        return Watcher(args).run()
    except WatcherError as exc:
        print(f"watcher configuration error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
