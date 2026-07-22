from __future__ import annotations

import importlib.util
import json
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_PATH = REPO_ROOT / "scripts" / "ap" / "run_reference_solution_audit.py"
SPEC = importlib.util.spec_from_file_location("run_reference_solution_audit", SCRIPT_PATH)
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


def test_collect_results_fails_closed_on_duplicate_or_missing_trials(tmp_path: Path) -> None:
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


def test_benchmark_revision_uses_packaged_episode_without_git(tmp_path: Path) -> None:
    episode = tmp_path / "dataset_episode.json"
    _write_json(episode, {"benchmark_revision": "a" * 40})
    assert MODULE.benchmark_revision(tmp_path, episode) == "a" * 40


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
        _audit_payload(f"E{index}", strict_pass=index != 3)
        for index in range(1, 7)
    ]
    aggregate = WATCHER.aggregate_audits(payloads)
    assert aggregate["summary"]["total"] == 90
    assert aggregate["summary"]["passed"] == 75
    assert aggregate["summary"]["all_reference_solutions_pass"] is False
    assert aggregate["summary"]["by_environment"]["E3"]["passed"] == 0
