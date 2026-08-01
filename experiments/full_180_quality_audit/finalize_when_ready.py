#!/usr/bin/env python3
"""Build the first-pass 180-task audit once all five AP lanes are exported."""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BENCHMARK_REVISION = "27cdd816c6e33b2b19ef5d638aa47d7c06283070"
REFERENCE_AGENTHUB_REVISION = "c0fb2b2a34bdab8fddea9082dd38b85db466f4df"
HARBOR_REVISION = "071281b3d931aafd6a5375fa7d5933e23054d784"
DEFAULT_ROOT = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_20260802"
)
TERMINAL = {"Succeeded", "Failed", "Cancelled"}


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


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


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class Finalizer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = args.repo_root.resolve()
        self.root = args.audit_root.resolve()
        self.state_dir = self.root / "finalizer"
        self.analysis = self.root / "analysis"

    def heartbeat(self, phase: str, **fields: Any) -> None:
        atomic_json(
            self.state_dir / "heartbeat.json",
            {
                "updated_at_utc": utc_now(),
                "status": "active",
                "phase": phase,
                "pid": os.getpid(),
                "next_poll_seconds": self.args.poll_sec,
                **fields,
            },
        )

    def event(self, event: str, **fields: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state_dir / "events.jsonl").open(
            "a", encoding="utf-8"
        ) as handle:
            handle.write(
                json.dumps(
                    {"timestamp_utc": utc_now(), "event": event, **fields},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def run_command(
        self, command: list[str], *, timeout: int = 900
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        existing_pythonpath = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            f"{self.repo}{os.pathsep}{existing_pythonpath}"
            if existing_pythonpath
            else str(self.repo)
        )
        return subprocess.run(
            command,
            cwd=self.repo,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=timeout,
            check=False,
        )

    def readiness(self) -> tuple[dict[str, Any] | None, str | None]:
        control_state = read_json(
            self.root / "missing-control-watcher" / "state.json", {}
        )
        shuffled_group_id = control_state.get("shuffled_group_id")
        reference_group_id = control_state.get("reference_group_id")
        if not shuffled_group_id or not reference_group_id:
            return None, "waiting for shuffled/reference groups to be submitted"

        manifest = read_json(self.root / "watcher" / "manifest.json", {})
        group_ids = {
            str(row.get("group_id"))
            for row in manifest.get("groups", [])
            if isinstance(row, dict) and row.get("group_id")
        }
        if len(group_ids) != 5:
            return None, f"expected five tracked AP groups, found {len(group_ids)}"

        inventory = read_json(self.root / "watcher" / "inventory.json", {})
        jobs = [
            row
            for row in inventory.get("jobs", [])
            if isinstance(row, dict) and row.get("job_id")
        ]
        if len(jobs) != 30:
            return None, f"expected 30 environment jobs, found {len(jobs)}"
        nonterminal = [
            str(row["job_id"])
            for row in jobs
            if row.get("status") not in TERMINAL
        ]
        if nonterminal:
            return None, f"waiting for {len(nonterminal)} nonterminal jobs"

        incomplete_exports: list[str] = []
        for row in jobs:
            marker = read_json(
                self.root / "watcher" / "exports" / f"{row['job_id']}.json", {}
            )
            if marker.get("completed") is not True or marker.get("unsafe") is True:
                incomplete_exports.append(str(row["job_id"]))
        if incomplete_exports:
            return None, f"waiting for {len(incomplete_exports)} safe exports"

        failed = [
            {
                "job_id": row.get("job_id"),
                "group_id": row.get("group_id"),
                "instance_id": row.get("instance_id"),
                "status": row.get("status"),
                "error_code": row.get("error_code"),
            }
            for row in jobs
            if row.get("status") != "Succeeded"
        ]
        if failed:
            atomic_json(self.state_dir / "terminal_failures.json", {"jobs": failed})
            return None, f"{len(failed)} terminal environment jobs require repair"

        reference_jobs = [
            row for row in jobs if row.get("group_id") == reference_group_id
        ]
        if len(reference_jobs) != 6:
            return None, "reference group does not contain six environments"
        return {
            "jobs": jobs,
            "group_ids": sorted(group_ids),
            "shuffled_group_id": shuffled_group_id,
            "reference_group_id": reference_group_id,
        }, None

    def run_stage(self, name: str, command: list[str], timeout: int = 900) -> None:
        self.heartbeat("running_analysis", stage=name)
        result = self.run_command(command, timeout=timeout)
        if result.returncode != 0:
            diagnostic = (result.stderr.strip() or result.stdout.strip())[-3000:]
            raise RuntimeError(f"{name} failed: {diagnostic}")
        self.event("analysis_stage_completed", stage=name)

    def finalize(self, ready: dict[str, Any]) -> None:
        matrix_dir = self.analysis / "current-matrix"
        reference_path = self.analysis / "reference-full180.json"
        semantic_reviews_path = self.analysis / "semantic_reviews.json"
        ledger_dir = self.analysis / "ledger"
        report_dir = self.analysis / "report"
        matrix_dir.mkdir(parents=True, exist_ok=True)
        if not semantic_reviews_path.is_file():
            atomic_json(
                semantic_reviews_path,
                {"schema_version": "1.0", "reviews": []},
            )

        self.run_stage(
            "collect-four-condition-matrix",
            [
                sys.executable,
                str(self.repo / "scripts/ap/build_t56_oracle_study.py"),
                "--raw-root",
                str(self.root / "raw"),
                "--tasks-root",
                str(self.repo / "benchmark/tasks"),
                "--skills-root",
                str(self.repo / "benchmark/skills"),
                "--inventory",
                str(self.root / "watcher/inventory.json"),
                "--output-dir",
                str(matrix_dir),
            ],
        )
        self.run_stage(
            "aggregate-reference-full180",
            [
                sys.executable,
                str(self.repo / "scripts/ap/aggregate_reference_solution_audit.py"),
                "--export-root",
                str(self.root / "raw"),
                "--output",
                str(reference_path),
                "--expected-group-id",
                str(ready["reference_group_id"]),
                "--expected-dataset",
                "skillevolbench/skillevolbench",
                "--expected-split",
                "v1.1@18",
                "--expected-benchmark-revision",
                BENCHMARK_REVISION,
                "--expected-agenthub-ref",
                REFERENCE_AGENTHUB_REVISION,
                "--expected-harbor-revision",
                HARBOR_REVISION,
                "--expected-tiers",
                "1,2,3,4,5,6",
            ],
        )
        self.run_stage(
            "build-strict-180-ledger",
            [
                sys.executable,
                str(self.repo / "experiments/full_180_quality_audit/build_audit.py"),
                "--tasks-root",
                str(self.repo / "benchmark/tasks"),
                "--static-audit",
                str(self.root / "static-v1.1-head/all_task_verifier_audit.json"),
                "--legacy-behavior",
                "/cpfs02/user/zhangfengji.zfj/skillevolbench_v1_1_20260727/analysis/selfgen_behavior_audit.json",
                "--legacy-t56-report",
                "/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723/analysis/t56_report_data.json",
                "--v11-task-audit",
                str(self.repo / "docs/skillevolbench_v1_1_task_audit.json"),
                "--v11-reference-audit",
                str(reference_path),
                "--v11-regression",
                "/cpfs02/user/zhangfengji.zfj/skillevolbench_v1_1_20260727/regression-at12/analysis/v1_1_regression_audit.json",
                "--v11-full-evidence",
                str(matrix_dir / "t56_evidence.json"),
                "--semantic-reviews",
                str(semantic_reviews_path),
                "--expected-model",
                "qwen3.7-max",
                "--expected-benchmark-revision",
                BENCHMARK_REVISION,
                "--require-complete-current",
                "--output-dir",
                str(ledger_dir),
            ],
        )
        self.run_stage(
            "render-report",
            [
                sys.executable,
                str(self.repo / "experiments/full_180_quality_audit/build_report.py"),
                "--ledger",
                str(ledger_dir / "task_five_point_audit.json"),
                "--output-dir",
                str(report_dir),
            ],
        )

        outputs = [
            matrix_dir / "t56_evidence.json",
            matrix_dir / "t56_tasks.csv",
            reference_path,
            semantic_reviews_path,
            ledger_dir / "task_five_point_audit.json",
            ledger_dir / "task_five_point_audit.csv",
            report_dir / "report_summary.json",
            report_dir / "skillevolbench_180_five_point_audit_zh.md",
            report_dir / "skillevolbench_180_five_point_audit_zh.html",
        ]
        missing = [str(path) for path in outputs if not path.is_file() or path.stat().st_size == 0]
        if missing:
            raise RuntimeError(f"analysis outputs are missing or empty: {missing!r}")
        completed = {
            "completed_at_utc": utc_now(),
            "claim": "first_pass_180_task_five_point_screen",
            "group_ids": ready["group_ids"],
            "benchmark_revision": BENCHMARK_REVISION,
            "outputs": [
                {
                    "path": str(path),
                    "bytes": path.stat().st_size,
                    "sha256": sha256(path),
                }
                for path in outputs
            ],
        }
        atomic_json(self.state_dir / "completed.json", completed)
        self.heartbeat("completed", completed_path=str(self.state_dir / "completed.json"))
        self.event("first_pass_audit_completed")

    def step(self) -> bool:
        if (self.state_dir / "completed.json").is_file():
            self.heartbeat("completed")
            return True
        ready, reason = self.readiness()
        if ready is None:
            self.heartbeat("waiting_for_evidence", reason=reason)
            return False
        self.finalize(ready)
        return True

    def run(self) -> int:
        self.event("finalizer_started", pid=os.getpid())
        while True:
            try:
                if self.step():
                    return 0
            except (OSError, ValueError, RuntimeError, subprocess.SubprocessError) as exc:
                diagnostic = str(exc)[-3000:]
                self.event("finalizer_error", diagnostic=diagnostic)
                self.heartbeat("analysis_error", diagnostic=diagnostic)
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--poll-sec", type=int, default=120)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_sec < 10:
        parser.error("--poll-sec must be at least 10")
    return args


def main() -> int:
    args = parse_args()
    state_dir = args.audit_root.resolve() / "finalizer"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_handle = (state_dir / "finalizer.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 75
    return Finalizer(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
