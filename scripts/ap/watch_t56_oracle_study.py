#!/usr/bin/env python3
"""Durably monitor and export evidence for the T5/T6 oracle study.

The watcher is intentionally an operational evidence collector, not a scorer:
an AP ``Succeeded`` status only causes artifacts to be exported and audited.
Task pass/fail conclusions must still come from the benchmark reports and raw
verifier evidence.

The state directory contains a mutable manifest. New oracle jobs or groups can
be registered while the daemon is running; the next polling cycle adopts them.
No credentials are written to state or logs.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


TERMINAL_STATUSES = {"Succeeded", "Failed", "Cancelled"}
DEFAULT_STATE_DIR = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723/"
    "watcher"
)
DEFAULT_EVIDENCE_DIR = DEFAULT_STATE_DIR.parent / "raw"
DEFAULT_MANIFEST = {
    "schema_version": 1,
    "groups": [
        {
            "label": "qwen37max-selfgen-v1-13",
            "group_id": "group-8eed29c18ffc42108bd95baf36b61280-d2",
        },
        {
            "label": "sig-fable-selfgen-v1-13",
            "group_id": "group-ecfa197f6c38486684075ff7fc52f915-d2",
        },
    ],
    "jobs": [
        {
            "label": "qwen37max-e6-repair-v1-15",
            "job_id": "ap-skillevolbench-db6d3f92d0444481-d2",
        },
        {
            "label": "sig-fable-e3-repair-v1-15",
            "job_id": "ap-skillevolbench-5abdd1d973254ba8-d2",
        },
    ],
    "external_job_records": [
        {
            "label": "qwen37max-e1-repair-v1-15",
            "path": (
                "/cpfs02/user/zhangfengji.zfj/"
                "skillevolbench_stability_20260722/"
                "watch-qwen-e6-then-e1/submission.json"
            ),
        }
    ],
}


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


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return default


def write_json(path: Path, value: Any) -> None:
    atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def safe_label(value: str) -> str:
    cleaned = "".join(
        character if character.isalnum() or character in "-_" else "-"
        for character in value.strip()
    ).strip("-")
    if not cleaned:
        raise ValueError("label must contain an alphanumeric character")
    return cleaned[:120]


class WatcherError(RuntimeError):
    pass


class Watcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.state_dir = args.state_dir.resolve()
        self.evidence_dir = args.evidence_dir.resolve()
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.evidence_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.state_dir, 0o700)
        os.chmod(self.evidence_dir, 0o700)
        self.manifest_path = self.state_dir / "manifest.json"
        if not self.manifest_path.exists():
            write_json(self.manifest_path, DEFAULT_MANIFEST)
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        if not self.environment.get("AP_API_KEY"):
            raise WatcherError("required environment variable is missing: AP_API_KEY")
        self.secrets = [
            value
            for name, value in self.environment.items()
            if ("KEY" in name or "SECRET" in name or "TOKEN" in name)
            and len(value) >= 8
        ]
        self.last_inventory: dict[str, Any] = {}
        self.analysis_dir = self.state_dir.parent / "analysis"

    def redact(self, text: str) -> str:
        result = text
        for secret in self.secrets:
            result = result.replace(secret, "[REDACTED]")
        return result

    def event(self, event: str, **fields: Any) -> None:
        record = {"timestamp_utc": utc_now(), "event": event, **fields}
        line = self.redact(json.dumps(record, ensure_ascii=False, separators=(",", ":")))
        path = self.state_dir / "events.jsonl"
        with path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        os.chmod(path, 0o600)

    def heartbeat(self, phase: str, **fields: Any) -> None:
        statuses: dict[str, int] = {}
        export_states: dict[str, int] = {}
        for job in self.last_inventory.values():
            status = str(job.get("status") or "Unknown")
            export_state = str(job.get("export_state") or "not_started")
            statuses[status] = statuses.get(status, 0) + 1
            export_states[export_state] = export_states.get(export_state, 0) + 1
        payload = {
            "updated_at_utc": utc_now(),
            "watcher_status": "active",
            "phase": phase,
            "pid": os.getpid(),
            "tracked_jobs": len(self.last_inventory),
            "ap_status_counts": statuses,
            "export_state_counts": export_states,
            "next_poll_seconds": self.args.poll_sec,
            **fields,
        }
        write_json(self.state_dir / "heartbeat.json", payload)
        atomic_write(
            self.state_dir / "status.txt",
            "\n".join(f"{key}: {value}" for key, value in payload.items()) + "\n",
        )

    def run_command(
        self,
        command: list[str],
        *,
        timeout: int,
        phase: str,
        heartbeat_fields: dict[str, Any] | None = None,
    ) -> subprocess.CompletedProcess[str]:
        started = time.monotonic()
        process = subprocess.Popen(
            command,
            cwd=self.args.repo_root,
            env=self.environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        fields = heartbeat_fields or {}
        next_heartbeat = 0.0
        while process.poll() is None:
            elapsed_float = time.monotonic() - started
            elapsed = int(elapsed_float)
            if elapsed >= timeout:
                process.kill()
                stdout, stderr = process.communicate()
                diagnostic = self.redact(stderr.strip() or stdout.strip())[-1000:]
                raise WatcherError(
                    f"command timed out after {timeout}s during {phase}: {diagnostic}"
                )
            if elapsed_float >= next_heartbeat:
                self.heartbeat(phase, elapsed_seconds=elapsed, **fields)
                next_heartbeat = elapsed_float + self.args.command_heartbeat_sec
            time.sleep(min(1.0, max(0.1, timeout - elapsed_float)))
        stdout, stderr = process.communicate()
        return subprocess.CompletedProcess(
            command,
            process.returncode,
            self.redact(stdout),
            self.redact(stderr),
        )

    def run_ap_json(self, arguments: list[str]) -> dict[str, Any]:
        result = self.run_command(
            [self.args.ap_cli, *arguments],
            timeout=self.args.api_timeout_sec,
            phase="querying_ap",
        )
        if result.returncode != 0:
            diagnostic = result.stderr.strip() or result.stdout.strip()
            raise WatcherError(
                f"AP CLI failed with exit {result.returncode}: {diagnostic[-1000:]}"
            )
        try:
            value = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise WatcherError("AP CLI returned invalid JSON") from exc
        if not isinstance(value, dict):
            raise WatcherError("AP CLI JSON root is not an object")
        return value

    def load_manifest(self) -> dict[str, Any]:
        value = read_json(self.manifest_path, {})
        if not isinstance(value, dict) or value.get("schema_version") != 1:
            raise WatcherError("manifest.json is missing or has an unsupported schema")
        for key in ("groups", "jobs", "external_job_records"):
            if not isinstance(value.get(key, []), list):
                raise WatcherError(f"manifest field {key} must be a list")
        return value

    def discover_jobs(self) -> dict[str, dict[str, Any]]:
        manifest = self.load_manifest()
        tracked: dict[str, dict[str, Any]] = {}

        def adopt(job: dict[str, Any], label: str, source: str) -> None:
            job_id = str(job.get("job_id") or "")
            if not job_id or job.get("job_type", "default") != "default":
                return
            tracked[job_id] = {
                "job_id": job_id,
                "label": safe_label(label),
                "source": source,
                "instance_id": job.get("instance_id"),
                "group_id": job.get("group_id"),
                "status": job.get("status") or "Unknown",
                "error_code": job.get("error_code"),
                "created_at": job.get("created_at"),
                "updated_at": job.get("updated_at"),
            }

        for group in manifest.get("groups", []):
            if not isinstance(group, dict):
                continue
            group_id = str(group.get("group_id") or "")
            label = safe_label(str(group.get("label") or group_id))
            if not group_id:
                continue
            response = self.run_ap_json(
                [
                    "job",
                    "list",
                    "--group-id",
                    group_id,
                    "--format",
                    "json",
                    "--limit",
                    "100",
                ]
            )
            for job in response.get("jobs", []):
                if isinstance(job, dict):
                    instance = str(job.get("instance_id") or "unknown")
                    adopt(job, f"{label}-{instance}", f"group:{group_id}")

        explicit: list[dict[str, str]] = []
        for job in manifest.get("jobs", []):
            if isinstance(job, dict) and job.get("job_id"):
                explicit.append(
                    {
                        "job_id": str(job["job_id"]),
                        "label": safe_label(str(job.get("label") or job["job_id"])),
                    }
                )
        for record in manifest.get("external_job_records", []):
            if not isinstance(record, dict) or not record.get("path"):
                continue
            payload = read_json(Path(str(record["path"])), {})
            if isinstance(payload, dict) and payload.get("job_id"):
                explicit.append(
                    {
                        "job_id": str(payload["job_id"]),
                        "label": safe_label(str(record.get("label") or payload["job_id"])),
                    }
                )
        for item in explicit:
            response = self.run_ap_json(["job", "get", item["job_id"]])
            adopt(response, item["label"], "explicit")
        return tracked

    def export_marker(self, job_id: str) -> Path:
        return self.state_dir / "exports" / f"{job_id}.json"

    def export_state(self, job_id: str) -> str:
        marker = read_json(self.export_marker(job_id), {})
        if isinstance(marker, dict) and marker.get("completed") is True:
            return "complete"
        if isinstance(marker, dict) and marker.get("unsafe") is True:
            return "unsafe_quarantine"
        return "not_started"

    @staticmethod
    def audit_tree(root: Path) -> dict[str, Any]:
        suffix_counts: dict[str, int] = {}
        named_counts = {
            "full_report.json": 0,
            "result.json": 0,
            "trajectory.json": 0,
            "trajectory.jsonl": 0,
            "replay.jsonl": 0,
        }
        file_count = 0
        total_bytes = 0
        for directory, directory_names, file_names in os.walk(root, followlinks=False):
            directory_names[:] = [
                name
                for name in directory_names
                if not (Path(directory) / name).is_symlink()
            ]
            for name in file_names:
                path = Path(directory) / name
                if path.is_symlink() or not path.is_file():
                    continue
                file_count += 1
                try:
                    total_bytes += path.stat().st_size
                except OSError:
                    pass
                suffix = path.suffix.lower() or "<none>"
                suffix_counts[suffix] = suffix_counts.get(suffix, 0) + 1
                if name in named_counts:
                    named_counts[name] += 1
        return {
            "file_count": file_count,
            "total_bytes": total_bytes,
            "named_file_counts": named_counts,
            "suffix_counts": dict(sorted(suffix_counts.items())),
        }

    def export_job(self, job: dict[str, Any]) -> None:
        job_id = str(job["job_id"])
        label = safe_label(str(job["label"]))
        destination = self.evidence_dir / label / job_id
        marker_path = self.export_marker(job_id)
        marker_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if destination.exists() and not marker_path.exists():
            audit = self.audit_tree(destination)
            write_json(
                marker_path,
                {
                    "completed": True,
                    "adopted_existing": True,
                    "job_id": job_id,
                    "destination": str(destination),
                    "audited_at_utc": utc_now(),
                    "audit": audit,
                },
            )
            return
        if self.export_state(job_id) != "not_started":
            return

        temporary = destination.with_name(f".{job_id}.partial")
        if temporary.exists():
            shutil.rmtree(temporary)
        temporary.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.event("export_started", job_id=job_id, label=label)
        result = self.run_command(
            [
                self.args.ap_cli,
                "job",
                "export",
                job_id,
                "--output",
                str(temporary),
                "--logs",
                "--events",
            ],
            timeout=self.args.export_timeout_sec,
            phase="exporting_artifacts",
            heartbeat_fields={"current_job_id": job_id, "current_job_label": label},
        )
        if result.returncode != 0:
            diagnostic = (result.stderr.strip() or result.stdout.strip())[-1000:]
            raise WatcherError(f"export failed for {job_id}: {diagnostic}")

        scanner = self.args.repo_root / "scripts/ap/scan_export_safety.py"
        scan_result = self.run_command(
            [sys.executable, str(scanner), str(temporary)],
            timeout=self.args.scan_timeout_sec,
            phase="scanning_export",
            heartbeat_fields={"current_job_id": job_id, "current_job_label": label},
        )
        scan_payload: dict[str, Any] = {}
        try:
            scan_payload = json.loads(scan_result.stdout)
        except json.JSONDecodeError:
            pass
        if scan_result.returncode != 0:
            quarantine = self.evidence_dir / ".quarantine" / label / job_id
            quarantine.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            if quarantine.exists():
                shutil.rmtree(quarantine)
            temporary.replace(quarantine)
            write_json(
                marker_path,
                {
                    "completed": False,
                    "unsafe": True,
                    "job_id": job_id,
                    "quarantine": str(quarantine),
                    "scan_summary": scan_payload,
                    "recorded_at_utc": utc_now(),
                },
            )
            self.event("export_quarantined", job_id=job_id, label=label)
            return

        if destination.exists():
            shutil.rmtree(destination)
        temporary.replace(destination)
        audit = self.audit_tree(destination)
        marker = {
            "completed": True,
            "unsafe": False,
            "job_id": job_id,
            "label": label,
            "ap_status": job.get("status"),
            "destination": str(destination),
            "exported_at_utc": utc_now(),
            "scan_summary": scan_payload,
            "audit": audit,
        }
        write_json(marker_path, marker)
        self.event(
            "export_completed",
            job_id=job_id,
            label=label,
            file_count=audit["file_count"],
            total_bytes=audit["total_bytes"],
        )
        if label == "sig-fable-e2-oracle-exact-v1-16":
            validator = self.args.repo_root / "scripts/ap/validate_t56_oracle_smoke.py"
            validation_path = self.state_dir / "oracle-smoke-validation.json"
            validation = self.run_command(
                [
                    sys.executable,
                    str(validator),
                    str(destination),
                    "--tasks-root",
                    str(self.args.repo_root / "benchmark/tasks"),
                    "--output",
                    str(validation_path),
                ],
                timeout=self.args.analysis_timeout_sec,
                phase="validating_oracle_smoke",
                heartbeat_fields={"current_job_id": job_id},
            )
            self.event(
                "oracle_smoke_validated" if validation.returncode == 0 else "oracle_smoke_invalid",
                job_id=job_id,
                validation_path=str(validation_path),
            )

    def refresh_analysis(self, inventory: dict[str, dict[str, Any]]) -> None:
        """Refresh derived evidence only when its AP/export inputs changed."""
        signature_rows = [
            {
                "job_id": job_id,
                "status": job.get("status"),
                "updated_at": job.get("updated_at"),
                "export_state": self.export_state(job_id),
            }
            for job_id, job in sorted(inventory.items())
        ]
        signature = hashlib.sha256(
            json.dumps(signature_rows, sort_keys=True).encode("utf-8")
        ).hexdigest()
        marker_path = self.state_dir / "analysis.json"
        previous = read_json(marker_path, {})
        if (
            isinstance(previous, dict)
            and previous.get("input_signature") == signature
            and (self.analysis_dir / "t56_evidence.json").exists()
        ):
            return

        collector = self.args.repo_root / "scripts/ap/build_t56_oracle_study.py"
        result = self.run_command(
            [
                sys.executable,
                str(collector),
                "--raw-root",
                str(self.evidence_dir),
                "--tasks-root",
                str(self.args.repo_root / "benchmark/tasks"),
                "--skills-root",
                str(self.args.repo_root / "benchmark/skills"),
                "--inventory",
                str(self.state_dir / "inventory.json"),
                "--output-dir",
                str(self.analysis_dir),
            ],
            timeout=self.args.analysis_timeout_sec,
            phase="building_analysis",
        )
        if result.returncode != 0:
            diagnostic = (result.stderr.strip() or result.stdout.strip())[-1000:]
            self.event("analysis_refresh_failed", diagnostic=diagnostic)
            return
        payload: dict[str, Any] = {}
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError:
            pass
        write_json(
            marker_path,
            {
                "input_signature": signature,
                "refreshed_at_utc": utc_now(),
                "collector_result": payload,
            },
        )
        self.event("analysis_refreshed", **payload)

    def step(self) -> None:
        inventory = self.discover_jobs()
        for job_id, job in inventory.items():
            job["export_state"] = self.export_state(job_id)
        self.last_inventory = inventory
        write_json(
            self.state_dir / "inventory.json",
            {
                "updated_at_utc": utc_now(),
                "jobs": list(sorted(inventory.values(), key=lambda item: item["label"])),
            },
        )
        self.heartbeat("inventory_updated")

        if self.args.no_export:
            pending = sum(
                1
                for job in inventory.values()
                if job.get("status") not in TERMINAL_STATUSES
            )
            self.heartbeat(
                "observe_only",
                pending_nonterminal_jobs=pending,
                next_action="artifact export disabled by --no-export",
            )
            return

        for job_id in sorted(inventory, key=lambda key: inventory[key]["label"]):
            job = inventory[job_id]
            if job.get("status") not in TERMINAL_STATUSES:
                continue
            if self.export_state(job_id) == "not_started":
                self.export_job(job)
                job["export_state"] = self.export_state(job_id)
                self.last_inventory = inventory

        self.refresh_analysis(inventory)

        pending = sum(
            1
            for job in inventory.values()
            if job.get("status") not in TERMINAL_STATUSES
            or job.get("export_state") == "not_started"
        )
        self.heartbeat(
            "idle_waiting_for_jobs" if pending == 0 else "monitoring_jobs",
            pending_jobs_or_exports=pending,
            next_action=(
                "wait for new manifest entries"
                if pending == 0
                else "poll AP and export newly terminal jobs"
            ),
        )

    def run(self) -> int:
        self.event("watcher_started", pid=os.getpid())
        while True:
            try:
                self.step()
            except WatcherError as exc:
                diagnostic = self.redact(str(exc))[-1000:]
                self.event("transient_error", diagnostic=diagnostic)
                self.heartbeat(
                    "transient_error",
                    last_error=diagnostic,
                    next_action=f"retry after {self.args.error_backoff_sec}s",
                )
                if self.args.once:
                    return 1
                time.sleep(self.args.error_backoff_sec)
                continue
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def update_manifest(
    path: Path,
    collection: str,
    identity_key: str,
    identity_value: str,
    label: str,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    manifest = read_json(path, DEFAULT_MANIFEST)
    if not isinstance(manifest, dict):
        raise WatcherError("cannot update invalid manifest")
    entries = manifest.setdefault(collection, [])
    if not isinstance(entries, list):
        raise WatcherError(f"manifest field {collection} is not a list")
    replacement = {"label": safe_label(label), identity_key: identity_value}
    for index, entry in enumerate(entries):
        if isinstance(entry, dict) and entry.get(identity_key) == identity_value:
            entries[index] = replacement
            break
    else:
        entries.append(replacement)
    write_json(path, manifest)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--state-dir", type=Path, default=DEFAULT_STATE_DIR)
    parser.add_argument("--evidence-dir", type=Path, default=DEFAULT_EVIDENCE_DIR)
    parser.add_argument("--cluster", default="hk-benchmark-dev")
    parser.add_argument("--ap-cli", default="ap")
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument("--error-backoff-sec", type=int, default=60)
    parser.add_argument("--api-timeout-sec", type=int, default=120)
    parser.add_argument("--export-timeout-sec", type=int, default=3600)
    parser.add_argument("--scan-timeout-sec", type=int, default=1800)
    parser.add_argument("--analysis-timeout-sec", type=int, default=600)
    parser.add_argument("--command-heartbeat-sec", type=int, default=15)
    parser.add_argument("--once", action="store_true")
    parser.add_argument(
        "--no-export",
        action="store_true",
        help="query AP and update inventory without downloading artifacts",
    )
    parser.add_argument("--register-job", metavar="JOB_ID")
    parser.add_argument("--register-group", metavar="GROUP_ID")
    parser.add_argument("--label")
    args = parser.parse_args()
    if args.poll_sec < 5 or args.error_backoff_sec < 5:
        parser.error("poll and error backoff must be at least 5 seconds")
    if args.command_heartbeat_sec < 2:
        parser.error("command heartbeat must be at least 2 seconds")
    if args.register_job and args.register_group:
        parser.error("register only one job or one group at a time")
    if (args.register_job or args.register_group) and not args.label:
        parser.error("--label is required when registering an entity")
    return args


def main() -> int:
    args = parse_args()
    manifest_path = args.state_dir.resolve() / "manifest.json"
    if args.register_job:
        update_manifest(manifest_path, "jobs", "job_id", args.register_job, args.label)
        print(f"registered job {args.register_job}")
        return 0
    if args.register_group:
        update_manifest(
            manifest_path, "groups", "group_id", args.register_group, args.label
        )
        print(f"registered group {args.register_group}")
        return 0

    args.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_path = args.state_dir / "watcher.lock"
    lock_handle = lock_path.open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another watcher instance already holds the lock", file=sys.stderr)
        return 2
    return Watcher(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
