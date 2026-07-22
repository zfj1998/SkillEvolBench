#!/usr/bin/env python3
"""Run the official Harbor oracle against one environment's T4--T6 tasks.

This is a benchmark-integrity diagnostic, not a model baseline.  Harbor's
``oracle`` agent uploads and executes each task's checked-in
``solution/solve.sh`` inside the real task image, then runs the unchanged
official verifier.  The resulting audit answers a narrower question than an
oracle-skill model run: whether the task assets are internally solvable at all.
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import importlib.metadata
import json
import os
import shutil
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from skillevolbench.discovery import TaskRecord, TaskRegistry


EXPECTED_TASKS_PER_ENVIRONMENT = 15


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, UnicodeDecodeError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def benchmark_revision(repo_root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo_root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def harbor_provenance() -> dict[str, Any]:
    try:
        distribution = importlib.metadata.distribution("harbor")
    except importlib.metadata.PackageNotFoundError:
        return {"version": "missing", "installed_git_commit": None}
    direct_url_raw = distribution.read_text("direct_url.json")
    try:
        direct_url = json.loads(direct_url_raw) if direct_url_raw else {}
    except json.JSONDecodeError:
        direct_url = {}
    return {
        "version": distribution.version,
        "installed_git_commit": direct_url.get("vcs_info", {}).get("commit_id"),
    }


def select_tasks(repo_root: Path, environment_id: str) -> list[TaskRecord]:
    registry = TaskRegistry.from_disk(
        repo_root / "benchmark" / "skills",
        repo_root / "benchmark" / "tasks",
    )
    tasks = sorted(
        (
            task
            for task in registry.tasks
            if task.spec.environment_id == environment_id
            and task.spec.task_index in {4, 5, 6}
        ),
        key=lambda task: (task.spec.family_id, task.spec.task_index),
    )
    if len(tasks) != EXPECTED_TASKS_PER_ENVIRONMENT:
        raise RuntimeError(
            f"{environment_id} must contain exactly "
            f"{EXPECTED_TASKS_PER_ENVIRONMENT} T4-T6 tasks; got {len(tasks)}"
        )
    expected_ids = {
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in range(4, 7)
    }
    actual_ids = {task.spec.task_id for task in tasks}
    if actual_ids != expected_ids:
        raise RuntimeError(
            f"{environment_id} T4-T6 task IDs mismatch: "
            f"missing={sorted(expected_ids - actual_ids)}, "
            f"extra={sorted(actual_ids - expected_ids)}"
        )
    return tasks


def prepare_runtime_tasks(tasks: list[TaskRecord], runtime_root: Path) -> list[Path]:
    if runtime_root.exists():
        shutil.rmtree(runtime_root)
    runtime_root.mkdir(parents=True)
    paths: list[Path] = []
    for task in tasks:
        destination = runtime_root / task.spec.task_id
        shutil.copytree(task.folder, destination)
        paths.append(destination)
    return paths


async def run_harbor_oracle(
    *,
    task_paths: list[Path],
    jobs_dir: Path,
    job_name: str,
    concurrency: int,
) -> None:
    # Harbor is intentionally imported only in AP/DinD-capable runtimes.  This
    # keeps offline asset validation and unit tests usable without Harbor.
    from harbor.job import Job  # type: ignore
    from harbor.models.environment_type import EnvironmentType  # type: ignore
    from harbor.models.job.config import JobConfig  # type: ignore
    from harbor.models.trial.config import (  # type: ignore
        AgentConfig,
        EnvironmentConfig,
        TaskConfig,
        VerifierConfig,
    )

    config = JobConfig(
        job_name=job_name,
        jobs_dir=str(jobs_dir),
        tasks=[TaskConfig(path=str(path)) for path in task_paths],
        datasets=[],
        agents=[AgentConfig(name="oracle")],
        environment=EnvironmentConfig(type=EnvironmentType.DOCKER),
        verifier=VerifierConfig(),
        n_concurrent_trials=concurrency,
        n_attempts=1,
        artifacts=[],
    )
    job = await Job.create(config)
    await job.run()


def _reward(trial_dir: Path, result: dict[str, Any]) -> tuple[float | None, dict[str, Any]]:
    rewards = result.get("verifier_result", {}).get("rewards", {})
    if not isinstance(rewards, dict):
        rewards = {}
    reward_path = trial_dir / "verifier" / "reward.txt"
    normalized: float | None = None
    try:
        normalized = float(reward_path.read_text(encoding="utf-8").strip())
    except (FileNotFoundError, OSError, UnicodeDecodeError, ValueError):
        candidate = rewards.get("normalized_score")
        if isinstance(candidate, (int, float)):
            normalized = float(candidate)
    return normalized, rewards


def collect_results(
    *,
    tasks: list[TaskRecord],
    job_root: Path,
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for task in tasks:
        task_id = task.spec.task_id
        candidates = sorted(
            path
            for path in job_root.glob(f"{task_id}__*")
            if path.is_dir()
        )
        trial_dir = candidates[0] if len(candidates) == 1 else None
        result = read_json(trial_dir / "result.json") if trial_dir else {}
        score_report = (
            read_json(trial_dir / "verifier" / "score_report.json")
            if trial_dir
            else {}
        )
        normalized, rewards = (
            _reward(trial_dir, result) if trial_dir else (None, {})
        )
        outcome = rewards.get("outcome_passed")
        process = rewards.get("process_passed")
        exception = result.get("exception_info")
        strict_pass = bool(
            trial_dir is not None
            and result
            and exception is None
            and normalized is not None
            and abs(normalized - 1.0) <= 1e-9
            and float(outcome) == 1.0
            and float(process) == 1.0
        )
        rows.append(
            {
                "task_id": task_id,
                "task_slug": task.slug,
                "environment_id": task.spec.environment_id,
                "family_id": task.spec.family_id,
                "tier": task.spec.task_index,
                "role": task.spec.role.value,
                "trial_count": len(candidates),
                "trial_dir": str(trial_dir) if trial_dir else None,
                "result_present": bool(result),
                "exception_info": exception,
                "normalized_score": normalized,
                "outcome_passed": outcome,
                "process_passed": process,
                "total_score": score_report.get("total_score"),
                "max_score": score_report.get("max_score"),
                "strict_pass": strict_pass,
            }
        )
    return rows


def build_audit(
    *,
    repo_root: Path,
    environment_id: str,
    tasks: list[TaskRecord],
    jobs_dir: Path,
    job_name: str,
    run_error: str | None,
) -> dict[str, Any]:
    job_root = jobs_dir / job_name
    rows = collect_results(tasks=tasks, job_root=job_root)
    passed = sum(bool(row["strict_pass"]) for row in rows)
    by_tier = {
        str(tier): {
            "passed": sum(
                bool(row["strict_pass"]) for row in rows if row["tier"] == tier
            ),
            "total": sum(1 for row in rows if row["tier"] == tier),
        }
        for tier in (4, 5, 6)
    }
    return {
        "schema_version": "1.0",
        "audit_type": "official_reference_solution_via_harbor_oracle",
        "generated_at_utc": utc_now(),
        "environment_id": environment_id,
        "benchmark_revision": benchmark_revision(repo_root),
        "harbor": harbor_provenance(),
        "job_name": job_name,
        "job_root": str(job_root),
        "execution": {
            "agent": "oracle",
            "environment": "docker",
            "official_solution": "solution/solve.sh",
            "official_verifier": "tests/test.sh",
            "run_error": run_error,
        },
        "summary": {
            "passed": passed,
            "total": len(rows),
            "pass_rate": passed / len(rows) if rows else 0.0,
            "all_reference_solutions_pass": passed == len(rows) and run_error is None,
            "by_tier": by_tier,
        },
        "tasks": rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "task_id",
        "task_slug",
        "environment_id",
        "family_id",
        "tier",
        "role",
        "trial_count",
        "result_present",
        "normalized_score",
        "outcome_passed",
        "process_passed",
        "total_score",
        "max_score",
        "strict_pass",
        "trial_dir",
        "exception_info",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)


def write_metrics(path: Path, audit: dict[str, Any]) -> None:
    summary = audit["summary"]
    payload = {
        "task_score": 0.0,
        "passed": False,
        "scoreable": False,
        "status": "reference_solution_audit_complete",
        "environment_id": audit["environment_id"],
        "reference_solution_pass_rate": summary["pass_rate"],
        "reference_solution_passed": summary["passed"],
        "reference_solution_total": summary["total"],
        "all_reference_solutions_pass": summary["all_reference_solutions_pass"],
        "message": (
            "Non-canonical benchmark-integrity diagnostic; task_score is "
            "intentionally zero."
        ),
    }
    atomic_json(path, payload)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
    )
    parser.add_argument("--environment-id", choices=[f"E{i}" for i in range(1, 7)], required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workspace-root", type=Path, required=True)
    parser.add_argument("--concurrency", type=int, default=2)
    parser.add_argument("--job-name")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not 1 <= args.concurrency <= 4:
        raise SystemExit("--concurrency must be between 1 and 4")
    repo_root = args.repo_root.resolve()
    output_dir = args.output_dir.resolve()
    workspace_root = args.workspace_root.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    workspace_root.mkdir(parents=True, exist_ok=True)
    tasks = select_tasks(repo_root, args.environment_id)
    job_name = args.job_name or (
        f"reference_solution__{args.environment_id}__"
        + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    )
    runtime_root = workspace_root / "runtime" / args.environment_id
    jobs_dir = workspace_root / "harbor-job"
    task_paths = prepare_runtime_tasks(tasks, runtime_root)

    run_error: str | None = None
    try:
        asyncio.run(
            run_harbor_oracle(
                task_paths=task_paths,
                jobs_dir=jobs_dir,
                job_name=job_name,
                concurrency=args.concurrency,
            )
        )
    except BaseException as exc:  # preserve partial trials for diagnosis
        run_error = f"{type(exc).__name__}: {exc}"

    audit = build_audit(
        repo_root=repo_root,
        environment_id=args.environment_id,
        tasks=tasks,
        jobs_dir=jobs_dir,
        job_name=job_name,
        run_error=run_error,
    )
    atomic_json(output_dir / "reference_solution_audit.json", audit)
    write_csv(output_dir / "reference_solution_audit.csv", audit["tasks"])
    write_metrics(output_dir / "metrics.json", audit)

    # A failed reference solution is the result under investigation, not an AP
    # infrastructure failure.  Only fail the process when Harbor itself could
    # not produce one result per selected task.
    complete = all(
        row["trial_count"] == 1 and row["result_present"]
        for row in audit["tasks"]
    )
    if not complete:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
