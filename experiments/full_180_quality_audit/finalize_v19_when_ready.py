#!/usr/bin/env python3
"""Select valid v1.1@19 evidence and build the 180-row first-pass report.

This finalizer is retry-aware but never blends stateful episodes.  It accepts
one newest, safe, provenance-valid environment export for each of five lanes
and six environments, writes the exact 30-job selection, then runs the
condition collector, the all-tier reference audit, and the five-point ledger.
Failed and superseded attempts remain in the candidate audit for diagnosis.
"""

from __future__ import annotations

import argparse
import fcntl
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BENCHMARK_REVISION = "7ecf3fb9d30a551ca31ddcd7856a23e6c18b7b8f"
AGENTHUB_REVISION = "25f8c0becb4d17f8edf3a65767629569e4361827"
HARBOR_REVISION = "071281b3d931aafd6a5375fa7d5933e23054d784"
DATASET = "skillevolbench/skillevolbench"
DATASET_SPLIT = "v1.1@19"
MODEL = "qwen3.7-max"
ENVIRONMENTS = tuple(f"E{index}" for index in range(1, 7))
LANES = (
    "self_generated",
    "no_skill",
    "exact_curated",
    "shuffled",
    "reference",
)
LANE_LABELS = {
    "self_generated": "qwen37-v1-1-19-self-generated",
    "no_skill": "qwen37-v1-1-19-no-skill",
    "exact_curated": "qwen37-v1-1-19-exact-curated",
    "shuffled": "qwen37-v1-1-19-shuffled",
    "reference": "qwen37-v1-1-19-reference",
}
TERMINAL = {"Succeeded", "Failed", "Cancelled"}
HEX64 = re.compile(r"^[0-9a-f]{64}$")
PRUNED_PATH = re.compile(
    r"^runs/[^/]+/harbor-job/[^/]+/[^/]+/agent/opencode/xdg-data$"
)
DEFAULT_ROOT = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_v1_1_19_20260802"
)


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
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def lane_from_label(label: Any) -> str | None:
    value = str(label or "")
    for lane, prefix in LANE_LABELS.items():
        if value == prefix or any(value == f"{prefix}-{env}" for env in ENVIRONMENTS):
            return lane
    return None


def expected_task_ids(environment: str, tiers: tuple[int, ...]) -> set[str]:
    return {
        f"{environment}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in tiers
    }


class V19Finalizer:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = args.repo_root.resolve()
        self.root = args.audit_root.resolve()
        self.state_dir = self.root / "v19-finalizer"
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
                "benchmark_revision": BENCHMARK_REVISION,
                "agenthub_revision": AGENTHUB_REVISION,
                "dataset_split": DATASET_SPLIT,
                **fields,
            },
        )

    def event(self, event: str, **fields: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                json.dumps(
                    {"timestamp_utc": utc_now(), "event": event, **fields},
                    ensure_ascii=False,
                )
                + "\n"
            )

    def _candidate_errors(
        self, row: dict[str, Any], lane: str, environment: str
    ) -> tuple[list[str], dict[str, Any]]:
        errors: list[str] = []
        job_id = str(row.get("job_id") or "")
        marker = read_json(self.root / "watcher/exports" / f"{job_id}.json", {})
        if marker.get("completed") is not True:
            errors.append("safe export is incomplete")
        if marker.get("unsafe") is True:
            errors.append("export is quarantined")
        scan = marker.get("scan_summary") or {}
        if scan.get("clean") is not True or scan.get("scan_complete") is not True:
            errors.append("export safety scan is not complete and clean")
        destination = Path(str(marker.get("destination") or ""))
        raw_root = (self.root / "raw").resolve()
        try:
            resolved_destination = destination.resolve(strict=True)
        except OSError:
            resolved_destination = destination
            errors.append("export destination is missing")
        if not resolved_destination.is_relative_to(raw_root):
            errors.append("export destination escapes the v1.1@19 raw root")
        output = resolved_destination / "artifacts/output"
        job = read_json(resolved_destination / "job.json", {})
        episode = read_json(output / "dataset_episode.json", {})
        if row.get("status") != "Succeeded" or job.get("status") != "Succeeded":
            errors.append("AP job is not Succeeded")
        if row.get("instance_id") != environment or job.get("instance_id") != environment:
            errors.append("environment identity mismatch")
        if job.get("job_id") != job_id:
            errors.append("job identity mismatch")
        if job.get("template_commit") != AGENTHUB_REVISION:
            errors.append("Agent-Hub template commit mismatch")
        if job.get("agenthub_revision") != AGENTHUB_REVISION:
            errors.append("Agent-Hub requested revision mismatch")
        episode_checks = {
            "dataset": DATASET,
            "split": DATASET_SPLIT,
            "benchmark_revision": BENCHMARK_REVISION,
            "environment_id": environment,
            "instance_id": environment,
            "primary_task_count": 30,
        }
        if any(episode.get(key) != value for key, value in episode_checks.items()):
            errors.append("dataset episode provenance mismatch")

        if lane == "reference":
            audits = list(output.glob("reference_solution_audit.json"))
            if len(audits) != 1:
                errors.append("reference audit artifact is missing or ambiguous")
            else:
                audit = read_json(audits[0], {})
                tasks = audit.get("tasks")
                actual_ids = {
                    str(task.get("task_id"))
                    for task in tasks or []
                    if isinstance(task, dict)
                }
                if audit.get("benchmark_revision") != BENCHMARK_REVISION:
                    errors.append("reference audit benchmark revision mismatch")
                if (audit.get("execution") or {}).get("agent") != "oracle":
                    errors.append("reference audit did not use the oracle agent")
                if (audit.get("harbor") or {}).get("installed_git_commit") != HARBOR_REVISION:
                    errors.append("reference audit Harbor revision mismatch")
                if (
                    not isinstance(tasks, list)
                    or len(tasks) != 30
                    or actual_ids != expected_task_ids(environment, (1, 2, 3, 4, 5, 6))
                    or any(
                        not isinstance(task, dict)
                        or type(task.get("strict_pass")) is not bool
                        or task.get("trial_count") != 1
                        or task.get("result_present") is not True
                        for task in tasks or []
                    )
                ):
                    errors.append("reference audit does not contain one complete 30-task grid")
        else:
            manifest = read_json(output / "ap_run_manifest.json", {})
            metrics = read_json(output / "metrics.json", {})
            pruning = read_json(output / "runtime_artifact_pruning_manifest.json", {})
            reports = list((output / "runs").glob("*/reports/full_report.json"))
            expected_count = 30 if lane == "self_generated" else 15
            expected_baseline = {
                "self_generated": "selfgen_in_session_always",
                "no_skill": "no_skill",
                "exact_curated": "curated_static",
                "shuffled": "curated_static",
            }[lane]
            expected_evaluation_only = lane != "self_generated"
            expected_canonical = lane == "self_generated"
            manifest_checks = {
                "benchmark_revision": BENCHMARK_REVISION,
                "environment_id": environment,
                "baseline_name": expected_baseline,
                "model": MODEL,
                "harbor_agent": "opencode",
                "canonical": expected_canonical,
                "evaluation_only_t4_t6": expected_evaluation_only,
                "oracle_skill_view": lane == "exact_curated",
                "shuffled_skill_view": lane == "shuffled",
                "within_env_replay": False,
                "replay_eval": False,
                "learning_max_attempts": 3 if lane == "self_generated" else 1,
            }
            if any(manifest.get(key) != value for key, value in manifest_checks.items()):
                errors.append("model run manifest does not match the lane protocol")
            if metrics.get("n_reflection_task_workspace_violations") != 0:
                errors.append("reflection workspace policy violation recorded")
            report = read_json(reports[0], {}) if len(reports) == 1 else {}
            if len(reports) != 1 or report.get("n_tasks_attempted") != expected_count:
                errors.append("full report task count mismatch")
            if (report.get("reflection") or {}).get("n_task_workspace_violations") != 0:
                errors.append("task workspace policy violation recorded")
            records = pruning.get("removed_directories")
            if (
                pruning.get("removed_directory_count") != expected_count
                or not isinstance(records, list)
                or len(records) != expected_count
            ):
                errors.append("runtime pruning count mismatch")
            elif any(
                not isinstance(record, dict)
                or PRUNED_PATH.fullmatch(str(record.get("path") or "")) is None
                or HEX64.fullmatch(str(record.get("tree_sha256") or "")) is None
                or HEX64.fullmatch(
                    str(record.get("canonical_trajectory_sha256") or "")
                )
                is None
                or HEX64.fullmatch(
                    str(record.get("canonical_session_export_sha256") or "")
                )
                is None
                or (output / str(record.get("path") or "")).exists()
                for record in records
            ):
                errors.append("runtime pruning record or canonical export hash is invalid")
            summary_keys = (
                "schema_version",
                "policy",
                "manifest",
                "removed_directory_count",
                "removed_regular_file_count",
                "removed_regular_file_bytes",
                "removed_symlink_count",
            )
            pruning_summary = {key: pruning.get(key) for key in summary_keys}
            if not (
                manifest.get("runtime_artifact_pruning")
                == metrics.get("runtime_artifact_pruning")
                == pruning_summary
            ):
                errors.append("runtime pruning provenance is not bound into metrics")
        return sorted(set(errors)), {
            "marker_path": str(
                self.root / "watcher/exports" / f"{job_id}.json"
            ),
            "destination": str(resolved_destination),
        }

    @staticmethod
    def _newest(row: dict[str, Any]) -> tuple[int, str, str]:
        attempt = row.get("attempt")
        return (
            attempt if type(attempt) is int else -1,
            str(row.get("updated_at") or row.get("created_at") or ""),
            str(row.get("job_id") or ""),
        )

    def readiness(self) -> tuple[dict[str, Any] | None, str | None]:
        controller = read_json(self.root / "matrix-controller/state.json", {})
        expected_controller = {
            "benchmark_revision": BENCHMARK_REVISION,
            "agenthub_revision": AGENTHUB_REVISION,
            "dataset_split": DATASET_SPLIT,
            "model": MODEL,
        }
        if any(controller.get(key) != value for key, value in expected_controller.items()):
            return None, "waiting for the exact v1.1@19 matrix controller state"
        group_ids = controller.get("group_ids") or {}
        if set(group_ids) != set(LANES) or not all(group_ids.values()):
            return None, "waiting for all five v1.1@19 groups to be submitted"
        if (controller.get("smoke_gate") or {}).get("status") != "passed":
            return None, "waiting for the self-generated E1 protocol smoke"

        inventory_payload = read_json(self.root / "watcher/inventory.json", {})
        jobs = [
            row
            for row in inventory_payload.get("jobs", [])
            if isinstance(row, dict) and lane_from_label(row.get("label"))
        ]
        candidates_by_key: dict[tuple[str, str], list[dict[str, Any]]] = {
            (lane, environment): []
            for lane in LANES
            for environment in ENVIRONMENTS
        }
        audit_rows: list[dict[str, Any]] = []
        for row in jobs:
            lane = lane_from_label(row.get("label"))
            environment = str(row.get("instance_id") or "")
            if lane is None or environment not in ENVIRONMENTS:
                continue
            errors, evidence = self._candidate_errors(row, lane, environment)
            audited = {
                **row,
                "lane": lane,
                "validation_errors": errors,
                "provenance_valid": not errors,
                **evidence,
            }
            audit_rows.append(audited)
            candidates_by_key[(lane, environment)].append(audited)

        selected: list[dict[str, Any]] = []
        missing: list[dict[str, Any]] = []
        for key, candidates in candidates_by_key.items():
            valid = [candidate for candidate in candidates if candidate["provenance_valid"]]
            if valid:
                selected.append(max(valid, key=self._newest))
                continue
            statuses = sorted({str(candidate.get("status")) for candidate in candidates})
            missing.append(
                {
                    "lane": key[0],
                    "environment_id": key[1],
                    "candidate_count": len(candidates),
                    "statuses": statuses,
                    "has_nonterminal": (
                        not candidates
                        or any(
                            candidate.get("status") not in TERMINAL
                            for candidate in candidates
                        )
                    ),
                }
            )

        selected_ids = {row["job_id"] for row in selected}
        for row in audit_rows:
            row["selected"] = row.get("job_id") in selected_ids
        atomic_json(
            self.state_dir / "candidate_validation.json",
            {
                "generated_at_utc": utc_now(),
                "candidate_count": len(audit_rows),
                "selected_count": len(selected),
                "missing": missing,
                "candidates": audit_rows,
            },
        )
        if missing:
            waiting = sum(item["has_nonterminal"] for item in missing)
            repair = len(missing) - waiting
            return None, (
                f"waiting for {waiting} lane/environment cells; "
                f"{repair} cells require a valid retry"
            )
        if len(selected) != 30:
            return None, f"expected 30 selected jobs, found {len(selected)}"

        selected.sort(key=lambda row: (LANES.index(row["lane"]), row["instance_id"]))
        selected_inventory = {
            "schema_version": 1,
            "generated_at_utc": utc_now(),
            "selection_rule": "newest_safe_provenance_valid_whole_environment",
            "benchmark_revision": BENCHMARK_REVISION,
            "agenthub_revision": AGENTHUB_REVISION,
            "dataset_split": DATASET_SPLIT,
            "jobs": selected,
        }
        selected_path = self.state_dir / "selected_inventory.json"
        atomic_json(selected_path, selected_inventory)
        reference_path = self.state_dir / "selected_reference_inventory.json"
        atomic_json(
            reference_path,
            {
                **{key: value for key, value in selected_inventory.items() if key != "jobs"},
                "jobs": [row for row in selected if row["lane"] == "reference"],
            },
        )
        return {
            "jobs": selected,
            "selected_inventory": selected_path,
            "selected_reference_inventory": reference_path,
            "group_ids": group_ids,
        }, None

    def run_command(
        self, command: list[str], *, timeout: int = 900
    ) -> subprocess.CompletedProcess[str]:
        environment = os.environ.copy()
        existing = environment.get("PYTHONPATH")
        environment["PYTHONPATH"] = (
            f"{self.repo}{os.pathsep}{existing}" if existing else str(self.repo)
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
                {
                    "schema_version": "1.0",
                    "benchmark_revision": BENCHMARK_REVISION,
                    "reviews": [],
                },
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
                str(ready["selected_inventory"]),
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
                "--selected-inventory",
                str(ready["selected_reference_inventory"]),
                "--expected-dataset",
                DATASET,
                "--expected-split",
                DATASET_SPLIT,
                "--expected-benchmark-revision",
                BENCHMARK_REVISION,
                "--expected-agenthub-ref",
                AGENTHUB_REVISION,
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
                str(self.root / "static/all_task_verifier_audit.json"),
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
                MODEL,
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
            ready["selected_inventory"],
            self.state_dir / "candidate_validation.json",
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
        missing = [
            str(path) for path in outputs if not path.is_file() or path.stat().st_size == 0
        ]
        if missing:
            raise RuntimeError(f"analysis outputs are missing or empty: {missing!r}")
        completed = {
            "completed_at_utc": utc_now(),
            "claim": "dynamic_first_pass_ready_for_manual_review_and_repeats",
            "benchmark_revision": BENCHMARK_REVISION,
            "agenthub_revision": AGENTHUB_REVISION,
            "dataset_split": DATASET_SPLIT,
            "selected_job_count": 30,
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
        self.event("dynamic_first_pass_completed")

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
        self.event("v19_finalizer_started", pid=os.getpid())
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
    state_dir = args.audit_root.resolve() / "v19-finalizer"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_handle = (state_dir / "finalizer.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 75
    return V19Finalizer(args).run()


if __name__ == "__main__":
    raise SystemExit(main())
