from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ap" / "run_reference_solution_audit.py"
SPEC = importlib.util.spec_from_file_location(
    "run_reference_solution_audit", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)

WATCHER_PATH = REPO_ROOT / "scripts" / "ap" / "watch_reference_solution_audit.py"
WATCHER_SPEC = importlib.util.spec_from_file_location(
    "watch_reference_solution_audit", WATCHER_PATH
)
assert WATCHER_SPEC and WATCHER_SPEC.loader
WATCHER = importlib.util.module_from_spec(WATCHER_SPEC)
WATCHER_SPEC.loader.exec_module(WATCHER)

AGGREGATOR_PATH = (
    REPO_ROOT / "scripts" / "ap" / "aggregate_reference_solution_audit.py"
)
AGGREGATOR_SPEC = importlib.util.spec_from_file_location(
    "aggregate_reference_solution_audit", AGGREGATOR_PATH
)
assert AGGREGATOR_SPEC and AGGREGATOR_SPEC.loader
AGGREGATOR = importlib.util.module_from_spec(AGGREGATOR_SPEC)
AGGREGATOR_SPEC.loader.exec_module(AGGREGATOR)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def test_selects_exactly_one_t4_t6_grid_per_environment() -> None:
    tasks = MODULE.select_tasks(REPO_ROOT, "E2")
    assert len(tasks) == 15
    assert [task.spec.task_index for task in tasks] == [4, 5, 6] * 5
    assert {task.spec.family_id for task in tasks} == {
        f"E2-LS{index}" for index in range(1, 6)
    }


def test_selects_all_thirty_tasks_for_full_environment_integrity_audit() -> None:
    tasks = MODULE.select_tasks(REPO_ROOT, "E2", (1, 2, 3, 4, 5, 6))
    assert len(tasks) == 30
    assert [task.spec.task_index for task in tasks] == [1, 2, 3, 4, 5, 6] * 5
    assert len({task.spec.task_id for task in tasks}) == 30


def test_collect_results_requires_full_outcome_and_process_pass(tmp_path: Path) -> None:
    tasks = MODULE.select_tasks(REPO_ROOT, "E2")[:2]
    job_root = tmp_path / "jobs" / "reference"
    for index, task in enumerate(tasks):
        trial = job_root / f"{task.spec.task_id}__trial{index}"
        rewards = {
            "normalized_score": 1.0,
            "outcome_passed": 1.0,
            "process_passed": 1.0 if index == 0 else 0.0,
        }
        _write_json(
            trial / "result.json",
            {"verifier_result": {"rewards": rewards}, "exception_info": None},
        )
        _write_json(
            trial / "verifier" / "score_report.json",
            {"total_score": 100.0, "max_score": 100.0},
        )
        (trial / "verifier" / "reward.txt").write_text("1.0\n", encoding="utf-8")

    rows = MODULE.collect_results(tasks=tasks, job_root=job_root)
    assert rows[0]["strict_pass"] is True
    assert rows[1]["strict_pass"] is False


def test_collect_results_fails_closed_on_duplicate_or_missing_trials(
    tmp_path: Path,
) -> None:
    tasks = MODULE.select_tasks(REPO_ROOT, "E6")[:2]
    job_root = tmp_path / "jobs" / "reference"
    first = tasks[0].spec.task_id
    for suffix in ("one", "two"):
        _write_json(job_root / f"{first}__{suffix}" / "result.json", {})

    rows = MODULE.collect_results(tasks=tasks, job_root=job_root)
    assert rows[0]["trial_count"] == 2
    assert rows[0]["strict_pass"] is False
    assert rows[1]["trial_count"] == 0
    assert rows[1]["strict_pass"] is False


def test_collect_results_accepts_normalized_only_verifier(tmp_path: Path) -> None:
    task = MODULE.select_tasks(REPO_ROOT, "E5")[0]
    job_root = tmp_path / "jobs" / "reference"
    trial = job_root / f"{task.spec.task_id}__trial"
    _write_json(
        trial / "result.json",
        {
            "verifier_result": {"rewards": {"normalized_score": 1.0}},
            "exception_info": None,
        },
    )
    (trial / "verifier").mkdir(parents=True, exist_ok=True)
    (trial / "verifier" / "reward.txt").write_text("1.0\n", encoding="utf-8")

    row = MODULE.collect_results(tasks=[task], job_root=job_root)[0]
    assert row["outcome_passed"] is None
    assert row["process_passed"] is None
    assert row["strict_pass"] is True


def test_benchmark_revision_uses_packaged_episode_without_git(tmp_path: Path) -> None:
    episode = tmp_path / "dataset_episode.json"
    _write_json(episode, {"benchmark_revision": "a" * 40})
    assert MODULE.benchmark_revision(tmp_path, episode) == "a" * 40


def test_harbor_provenance_uses_exported_runtime(tmp_path: Path) -> None:
    runtime = tmp_path / "harbor_runtime.json"
    _write_json(
        runtime,
        {"version": "0.1.0", "installed_git_commit": "b" * 40},
    )
    assert MODULE.harbor_provenance(runtime) == {
        "version": "0.1.0",
        "installed_git_commit": "b" * 40,
    }


def _audit_payload(environment_id: str, *, strict_pass: bool = True) -> dict:
    rows = []
    for task_id in sorted(WATCHER.expected_task_ids(environment_id)):
        rows.append(
            {
                "task_id": task_id,
                "environment_id": environment_id,
                "tier": int(task_id[-1]),
                "trial_count": 1,
                "result_present": True,
                "strict_pass": strict_pass,
            }
        )
    return {
        "audit_type": "official_reference_solution_via_harbor_oracle",
        "environment_id": environment_id,
        "benchmark_revision": WATCHER.BENCHMARK_REVISION,
        "harbor": {"installed_git_commit": WATCHER.HARBOR_REVISION},
        "execution": {"agent": "oracle"},
        "tasks": rows,
    }


def test_reference_watcher_validates_exact_task_grid_and_provenance() -> None:
    payload = _audit_payload("E2")
    valid, errors = WATCHER.validate_audit(payload, "E2")
    assert valid is True
    assert errors == []

    payload["tasks"].pop()
    valid, errors = WATCHER.validate_audit(payload, "E2")
    assert valid is False
    assert "task row count is not 15" in errors
    assert "T4-T6 task grid mismatch" in errors


def test_reference_watcher_accepts_exact_packaged_revision_fallback() -> None:
    payload = _audit_payload("E2")
    payload["benchmark_revision"] = "unknown"
    valid, errors = WATCHER.validate_audit(
        payload,
        "E2",
        packaged_benchmark_revision=WATCHER.BENCHMARK_REVISION,
    )
    assert valid is True
    assert errors == []

    valid, errors = WATCHER.validate_audit(
        payload,
        "E2",
        packaged_benchmark_revision="b" * 40,
    )
    assert valid is False
    assert "benchmark_revision mismatch" in errors


def test_reference_watcher_aggregates_all_90_tasks() -> None:
    payloads = [
        _audit_payload(f"E{index}", strict_pass=index != 3) for index in range(1, 7)
    ]
    aggregate = WATCHER.aggregate_audits(payloads)
    assert aggregate["summary"]["total"] == 90
    assert aggregate["summary"]["passed"] == 75
    assert aggregate["summary"]["all_reference_solutions_pass"] is False
    assert aggregate["summary"]["by_environment"]["E3"]["passed"] == 0


def test_reference_export_aggregator_accepts_all_180_tasks(tmp_path: Path) -> None:
    group_id = "group-full-reference"
    benchmark_revision = "b" * 40
    agenthub_revision = "a" * 40
    harbor_revision = "h" * 40
    export_root = tmp_path / "export"
    for environment_number in range(1, 7):
        environment_id = f"E{environment_number}"
        job_id = f"job-{environment_id}"
        output = export_root / "jobs" / job_id / "artifacts" / "output"
        rows = [
            {
                "task_id": f"{environment_id}-LS{family}-T{tier}",
                "environment_id": environment_id,
                "family_id": f"{environment_id}-LS{family}",
                "tier": tier,
                "strict_pass": True,
                "normalized_score": 1.0,
                "trial_count": 1,
                "result_present": True,
                "exception_info": None,
                "outcome_passed": 1.0,
                "process_passed": 1.0,
            }
            for family in range(1, 6)
            for tier in range(1, 7)
        ]
        _write_json(
            export_root / "jobs" / job_id / "job.json",
            {
                "job_id": job_id,
                "instance_id": environment_id,
                "group_id": group_id,
                "status": "Succeeded",
                "attempt": 0,
                "agenthub_revision": agenthub_revision,
            },
        )
        _write_json(
            output / "dataset_episode.json",
            {
                "environment_id": environment_id,
                "dataset": "dataset/name",
                "split": "v1.1@test",
                "benchmark_revision": benchmark_revision,
            },
        )
        _write_json(
            output / "reference_solution_audit.json",
            {
                "benchmark_revision": benchmark_revision,
                "harbor": {"installed_git_commit": harbor_revision},
                "execution": {"agent": "oracle"},
                "tasks": rows,
            },
        )

    output_path = tmp_path / "aggregate.json"
    result = subprocess.run(
        [
            sys.executable,
            str(AGGREGATOR_PATH),
            "--export-root",
            str(export_root),
            "--output",
            str(output_path),
            "--expected-group-id",
            group_id,
            "--expected-dataset",
            "dataset/name",
            "--expected-split",
            "v1.1@test",
            "--expected-benchmark-revision",
            benchmark_revision,
            "--expected-agenthub-ref",
            agenthub_revision,
            "--expected-harbor-revision",
            harbor_revision,
            "--expected-tiers",
            "1,2,3,4,5,6",
        ],
        text=True,
        capture_output=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr
    aggregate = json.loads(output_path.read_text(encoding="utf-8"))
    assert aggregate["tiers"] == [1, 2, 3, 4, 5, 6]
    assert aggregate["summary"] == {
        "passed": 180,
        "total": 180,
        "unique_task_ids": 180,
        "all_reference_solutions_pass": True,
        "by_tier": {
            str(tier): {"passed": 30, "total": 30}
            for tier in range(1, 7)
        },
    }


def test_reference_aggregator_discovers_only_matching_watcher_group(
    tmp_path: Path,
) -> None:
    wanted = tmp_path / "reference-E1" / "ap-reference-E1"
    foreign = tmp_path / "self-E1" / "ap-self-E1"
    _write_json(wanted / "job.json", {"group_id": "group-reference"})
    _write_json(foreign / "job.json", {"group_id": "group-self"})

    assert AGGREGATOR.group_job_dirs(tmp_path, "group-reference") == [wanted]
