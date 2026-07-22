#!/usr/bin/env python3
"""Advance and collect the official T4--T6 reference-solution AP audit."""

from __future__ import annotations

import argparse
import csv
import fcntl
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TERMINAL = {"Succeeded", "Failed", "Cancelled"}
SMOKE_JOB_ID = "ap-skillevolbench-6a1d35279aa4437b-d2"
AGENTHUB_REF = "ad4b38b9b35b9cc0c46f40f017d2fb6cbb096cc7"
BENCHMARK_REVISION = "8695f97c7db2a5c9098c951c7931681ca27d8532"
HARBOR_REVISION = "071281b3d931aafd6a5375fa7d5933e23054d784"
DEFAULT_ROOT = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723"
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def json_values(text: str) -> Iterable[Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        yield value


def find_group_id(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("group_id")
        if isinstance(direct, str) and direct.startswith("group-"):
            return direct
        for child in value.values():
            if found := find_group_id(child):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := find_group_id(child):
                return found
    return None


def expected_task_ids(environment_id: str) -> set[str]:
    return {
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in range(4, 7)
    }


def validate_audit(
    payload: Any,
    environment_id: str,
    *,
    packaged_benchmark_revision: str | None = None,
) -> tuple[bool, list[str]]:
    errors: list[str] = []
    if not isinstance(payload, dict):
        return False, ["audit root is not an object"]
    if payload.get("audit_type") != "official_reference_solution_via_harbor_oracle":
        errors.append("unexpected audit_type")
    if payload.get("environment_id") != environment_id:
        errors.append("environment_id mismatch")
    if (
        payload.get("benchmark_revision") != BENCHMARK_REVISION
        and packaged_benchmark_revision != BENCHMARK_REVISION
    ):
        errors.append("benchmark_revision mismatch")
    harbor = payload.get("harbor")
    if not isinstance(harbor, dict) or harbor.get("installed_git_commit") != HARBOR_REVISION:
        errors.append("Harbor revision mismatch")
    execution = payload.get("execution")
    if not isinstance(execution, dict) or execution.get("agent") != "oracle":
        errors.append("execution agent is not Harbor oracle")
    rows = payload.get("tasks")
    if not isinstance(rows, list) or len(rows) != 15:
        errors.append("task row count is not 15")
        rows = rows if isinstance(rows, list) else []
    actual = {str(row.get("task_id")) for row in rows if isinstance(row, dict)}
    if actual != expected_task_ids(environment_id):
        errors.append("T4-T6 task grid mismatch")
    for row in rows:
        if not isinstance(row, dict):
            errors.append("non-object task row")
            continue
        if row.get("trial_count") != 1 or row.get("result_present") is not True:
            errors.append(f"incomplete Harbor trial: {row.get('task_id')}")
    return not errors, errors


def find_one_audit(export_root: Path) -> Path | None:
    matches = sorted(export_root.rglob("reference_solution_audit.json"))
    return matches[0] if len(matches) == 1 else None


def aggregate_audits(payloads: list[dict[str, Any]]) -> dict[str, Any]:
    rows = [row for payload in payloads for row in payload.get("tasks", [])]
    by_environment: dict[str, Any] = {}
    for environment_id in [f"E{index}" for index in range(1, 7)]:
        selected = [row for row in rows if row.get("environment_id") == environment_id]
        by_environment[environment_id] = {
            "passed": sum(bool(row.get("strict_pass")) for row in selected),
            "total": len(selected),
            "by_tier": {
                str(tier): {
                    "passed": sum(
                        bool(row.get("strict_pass"))
                        for row in selected
                        if row.get("tier") == tier
                    ),
                    "total": sum(1 for row in selected if row.get("tier") == tier),
                }
                for tier in (4, 5, 6)
            },
        }
    return {
        "schema_version": "1.0",
        "audit_type": "official_reference_solution_all_environments",
        "generated_at_utc": utc_now(),
        "benchmark_revision": BENCHMARK_REVISION,
        "harbor_revision": HARBOR_REVISION,
        "summary": {
            "passed": sum(bool(row.get("strict_pass")) for row in rows),
            "total": len(rows),
            "all_reference_solutions_pass": bool(rows)
            and all(bool(row.get("strict_pass")) for row in rows),
            "by_environment": by_environment,
        },
        "tasks": rows,
    }


class Watcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = args.repo_root.resolve()
        self.root = args.study_root.resolve()
        self.state_dir = self.root / "reference-audit-watcher"
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_path = self.state_dir / "state.json"
        self.evidence_state = self.root / "watcher"
        self.analysis_dir = self.root / "analysis"
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        if not self.environment.get("AP_API_KEY"):
            raise RuntimeError("AP_API_KEY is required")
        self.secrets = [
            value
            for name, value in self.environment.items()
            if ("KEY" in name or "SECRET" in name or "TOKEN" in name)
            and len(value) >= 8
        ]
        self.state = self.load_state()

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def load_state(self) -> dict[str, Any]:
        value = read_json(self.state_path, {})
        if isinstance(value, dict) and value.get("schema_version") == 1:
            return value
        value = {
            "schema_version": 1,
            "created_at_utc": utc_now(),
            "smoke_job_id": SMOKE_JOB_ID,
            "full_group_id": None,
            "full_idempotency_key": str(uuid.uuid4()),
        }
        atomic_json(self.state_path, value)
        return value

    def save(self) -> None:
        self.state["updated_at_utc"] = utc_now()
        atomic_json(self.state_path, self.state)

    def heartbeat(self, phase: str, **fields: Any) -> None:
        atomic_json(
            self.state_dir / "heartbeat.json",
            {
                "updated_at_utc": utc_now(),
                "status": "active",
                "phase": phase,
                "pid": os.getpid(),
                "smoke_job_id": SMOKE_JOB_ID,
                "full_group_id": self.state.get("full_group_id"),
                **fields,
            },
        )

    def event(self, event: str, **fields: Any) -> None:
        line = self.redact(
            json.dumps({"timestamp_utc": utc_now(), "event": event, **fields}, ensure_ascii=False)
        )
        with (self.state_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

    def run(self, command: list[str], timeout: int = 300) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=self.repo,
            env=self.environment,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return subprocess.CompletedProcess(
            command,
            completed.returncode,
            self.redact(completed.stdout),
            self.redact(completed.stderr),
        )

    def ap_json(self, arguments: list[str]) -> dict[str, Any]:
        result = self.run([self.args.ap_cli, *arguments], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        value = json.loads(result.stdout)
        if not isinstance(value, dict):
            raise RuntimeError("AP returned a non-object JSON value")
        return value

    def job(self, job_id: str) -> dict[str, Any]:
        return self.ap_json(["job", "get", job_id])

    def group_jobs(self, group_id: str) -> list[dict[str, Any]]:
        value = self.ap_json(
            ["job", "list", "--group-id", group_id, "--format", "json", "--limit", "100"]
        )
        return [
            job
            for job in value.get("jobs", [])
            if isinstance(job, dict) and job.get("job_type", "default") == "default"
        ]

    def export_marker(self, job_id: str) -> dict[str, Any]:
        return read_json(self.evidence_state / "exports" / f"{job_id}.json", {})

    def exported_audit(self, job_id: str) -> dict[str, Any] | None:
        marker = self.export_marker(job_id)
        if not isinstance(marker, dict) or marker.get("completed") is not True:
            return None
        destination = marker.get("destination")
        if not isinstance(destination, str):
            return None
        audit_path = find_one_audit(Path(destination))
        if audit_path is None:
            return None
        value = read_json(audit_path, {})
        return value if isinstance(value, dict) else None

    def exported_dataset_episode(self, job_id: str) -> dict[str, Any] | None:
        marker = self.export_marker(job_id)
        if not isinstance(marker, dict) or marker.get("completed") is not True:
            return None
        destination = marker.get("destination")
        if not isinstance(destination, str):
            return None
        matches = sorted(Path(destination).rglob("dataset_episode.json"))
        if len(matches) != 1:
            return None
        value = read_json(matches[0], {})
        return value if isinstance(value, dict) else None

    def register_group(self, group_id: str) -> None:
        result = self.run(
            [
                sys.executable,
                str(self.repo / "scripts/ap/watch_t56_oracle_study.py"),
                "--state-dir",
                str(self.evidence_state),
                "--register-group",
                group_id,
                "--label",
                "reference-oracle-all-envs-v1-17",
            ],
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        self.state["registered_with_evidence_watcher"] = True
        self.save()

    def validate_smoke(self) -> tuple[bool, list[str]] | None:
        payload = self.exported_audit(SMOKE_JOB_ID)
        if payload is None:
            return None
        episode = self.exported_dataset_episode(SMOKE_JOB_ID) or {}
        packaged_revision = episode.get("benchmark_revision")
        valid, errors = validate_audit(
            payload,
            "E2",
            packaged_benchmark_revision=(
                packaged_revision if isinstance(packaged_revision, str) else None
            ),
        )
        atomic_json(
            self.state_dir / "smoke-validation.json",
            {
                "validated_at_utc": utc_now(),
                "valid": valid,
                "errors": errors,
                "strict_passed": payload.get("summary", {}).get("passed"),
                "strict_total": payload.get("summary", {}).get("total"),
                "audit_benchmark_revision": payload.get("benchmark_revision"),
                "packaged_benchmark_revision": packaged_revision,
                "benchmark_revision_evidence": (
                    "audit_json"
                    if payload.get("benchmark_revision") == BENCHMARK_REVISION
                    else "dataset_episode_json"
                ),
            },
        )
        return valid, errors

    def submit_full(self) -> None:
        command = [
            sys.executable,
            str(self.repo / "scripts/ap/submit.py"),
            "--scope",
            "full",
            "--cluster",
            self.args.cluster,
            "--agenthub-ref",
            AGENTHUB_REF,
            "--dataset",
            "skillevolbench/skillevolbench",
            "--split",
            "v1@17",
            "--reference-solution-audit",
            "--reference-audit-concurrency",
            "2",
            "--runtime-timeout-sec",
            "43200",
            "--concurrency",
            "3",
            "--suite-name",
            "skillevolbench-reference-oracle-v1-17",
            "--idempotency-key",
            str(self.state["full_idempotency_key"]),
        ]
        self.heartbeat("submitting_full_group")
        result = self.run(command, timeout=300)
        combined = result.stdout + "\n" + result.stderr
        group_id = next(
            (found for value in json_values(combined) if (found := find_group_id(value))),
            None,
        )
        if result.returncode != 0 or not group_id:
            self.state["last_submit_error"] = combined[-2000:]
            self.save()
            return
        self.state.update(
            {
                "full_group_id": group_id,
                "full_submitted_at_utc": utc_now(),
            }
        )
        self.state.pop("last_submit_error", None)
        self.save()
        self.register_group(group_id)
        self.event("full_group_submitted", group_id=group_id)

    def write_aggregate(self, jobs: list[dict[str, Any]]) -> bool:
        payloads: list[dict[str, Any]] = []
        errors: list[str] = []
        for job in jobs:
            job_id = str(job.get("job_id") or "")
            environment_id = str(job.get("instance_id") or "")
            payload = self.exported_audit(job_id)
            if payload is None:
                return False
            episode = self.exported_dataset_episode(job_id) or {}
            packaged_revision = episode.get("benchmark_revision")
            valid, audit_errors = validate_audit(
                payload,
                environment_id,
                packaged_benchmark_revision=(
                    packaged_revision if isinstance(packaged_revision, str) else None
                ),
            )
            if not valid:
                errors.extend(f"{environment_id}: {error}" for error in audit_errors)
            payloads.append(payload)
        if errors:
            atomic_json(self.state_dir / "full-validation-errors.json", errors)
            return False
        aggregate = aggregate_audits(payloads)
        if aggregate["summary"]["total"] != 90:
            return False
        self.analysis_dir.mkdir(parents=True, exist_ok=True)
        atomic_json(self.analysis_dir / "reference_solution_audit_all_envs.json", aggregate)
        csv_path = self.analysis_dir / "reference_solution_audit_all_envs.csv"
        fields = [
            "task_id",
            "task_slug",
            "environment_id",
            "family_id",
            "tier",
            "role",
            "normalized_score",
            "outcome_passed",
            "process_passed",
            "strict_pass",
            "trial_dir",
            "exception_info",
        ]
        with csv_path.open("w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
            writer.writeheader()
            writer.writerows(aggregate["tasks"])
        atomic_json(
            self.state_dir / "completed.json",
            {
                "completed_at_utc": utc_now(),
                "full_group_id": self.state.get("full_group_id"),
                "summary": aggregate["summary"],
            },
        )
        return True

    def step(self) -> bool:
        smoke = self.job(SMOKE_JOB_ID)
        smoke_status = str(smoke.get("status") or "Unknown")
        if smoke_status not in TERMINAL:
            self.heartbeat("waiting_for_smoke_terminal", smoke_status=smoke_status)
            return False
        if smoke_status != "Succeeded":
            self.heartbeat("smoke_failed", smoke_status=smoke_status)
            return False
        validation = self.validate_smoke()
        if validation is None:
            self.heartbeat("waiting_for_smoke_export", smoke_status=smoke_status)
            return False
        valid, errors = validation
        if not valid:
            self.heartbeat("smoke_invalid", validation_errors=errors)
            return False
        if not self.state.get("full_group_id"):
            self.submit_full()
            return False
        group_id = str(self.state["full_group_id"])
        if self.state.get("registered_with_evidence_watcher") is not True:
            self.register_group(group_id)
        jobs = self.group_jobs(group_id)
        statuses = [str(job.get("status") or "Unknown") for job in jobs]
        counts = {status: statuses.count(status) for status in sorted(set(statuses))}
        if len(jobs) != 6 or not all(status in TERMINAL for status in statuses):
            self.heartbeat("monitoring_full_group", job_count=len(jobs), job_statuses=counts)
            return False
        if self.write_aggregate(jobs):
            self.heartbeat("completed", job_count=6, job_statuses=counts)
            return True
        self.heartbeat("waiting_for_full_exports", job_count=6, job_statuses=counts)
        return False

    def loop(self) -> int:
        self.event("watcher_started", pid=os.getpid())
        while True:
            try:
                if self.step():
                    return 0
            except (RuntimeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                error = self.redact(f"{type(exc).__name__}: {exc}")[-1500:]
                self.event("transient_error", error=error)
                self.heartbeat("transient_error", error=error)
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--study-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--cluster", default="hk-benchmark-dev")
    parser.add_argument("--ap-cli", default="ap")
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_sec < 10:
        parser.error("--poll-sec must be at least 10")
    return args


def main() -> int:
    args = parse_args()
    state_dir = args.study_root.resolve() / "reference-audit-watcher"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (state_dir / "watcher.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another reference-audit watcher holds the lock", file=sys.stderr)
        return 75
    return Watcher(args).loop()


if __name__ == "__main__":
    raise SystemExit(main())
