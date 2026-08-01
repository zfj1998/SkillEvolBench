from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "experiments/full_180_quality_audit/finalize_v19_when_ready.py"
SPEC = importlib.util.spec_from_file_location("finalize_full_180_v19", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
FINAL = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(FINAL)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def make_finalizer(root: Path) -> object:
    return FINAL.V19Finalizer(
        SimpleNamespace(repo_root=ROOT, audit_root=root, poll_sec=10)
    )


def write_controller(root: Path) -> None:
    write_json(
        root / "matrix-controller/state.json",
        {
            "benchmark_revision": FINAL.BENCHMARK_REVISION,
            "agenthub_revision": FINAL.AGENTHUB_REVISION,
            "dataset_split": FINAL.DATASET_SPLIT,
            "model": FINAL.MODEL,
            "group_ids": {lane: f"group-{lane}" for lane in FINAL.LANES},
            "smoke_gate": {"status": "passed"},
        },
    )


def write_export(
    root: Path,
    *,
    lane: str,
    environment: str,
    job_id: str,
    attempt: int = 0,
    workspace_violations: int = 0,
) -> dict[str, object]:
    label = f"{FINAL.LANE_LABELS[lane]}-{environment}"
    destination = root / "raw" / label / job_id
    output = destination / "artifacts/output"
    write_json(
        root / f"watcher/exports/{job_id}.json",
        {
            "completed": True,
            "unsafe": False,
            "scan_summary": {"clean": True, "scan_complete": True},
            "destination": str(destination),
        },
    )
    write_json(
        destination / "job.json",
        {
            "job_id": job_id,
            "instance_id": environment,
            "group_id": f"group-{lane}",
            "status": "Succeeded",
            "attempt": attempt,
            "agenthub_revision": FINAL.AGENTHUB_REVISION,
            "template_commit": FINAL.AGENTHUB_REVISION,
        },
    )
    write_json(
        output / "dataset_episode.json",
        {
            "dataset": FINAL.DATASET,
            "split": FINAL.DATASET_SPLIT,
            "benchmark_revision": FINAL.BENCHMARK_REVISION,
            "environment_id": environment,
            "instance_id": environment,
            "primary_task_count": 30,
        },
    )
    if lane == "reference":
        write_json(
            output / "reference_solution_audit.json",
            {
                "benchmark_revision": FINAL.BENCHMARK_REVISION,
                "execution": {"agent": "oracle"},
                "harbor": {"installed_git_commit": FINAL.HARBOR_REVISION},
                "tasks": [
                    {
                        "task_id": task_id,
                        "strict_pass": True,
                        "trial_count": 1,
                        "result_present": True,
                    }
                    for task_id in sorted(
                        FINAL.expected_task_ids(environment, (1, 2, 3, 4, 5, 6))
                    )
                ],
            },
        )
    else:
        count = 30 if lane == "self_generated" else 15
        baseline = {
            "self_generated": "selfgen_in_session_always",
            "no_skill": "no_skill",
            "exact_curated": "curated_static",
            "shuffled": "curated_static",
        }[lane]
        summary = {
            "schema_version": 1,
            "policy": "remove-redundant-opencode-xdg-data-after-session-export",
            "manifest": "runtime_artifact_pruning_manifest.json",
            "removed_directory_count": count,
            "removed_regular_file_count": count,
            "removed_regular_file_bytes": count,
            "removed_symlink_count": 0,
        }
        write_json(
            output / "ap_run_manifest.json",
            {
                "benchmark_revision": FINAL.BENCHMARK_REVISION,
                "environment_id": environment,
                "baseline_name": baseline,
                "model": FINAL.MODEL,
                "harbor_agent": "opencode",
                "canonical": lane == "self_generated",
                "evaluation_only_t4_t6": lane != "self_generated",
                "oracle_skill_view": lane == "exact_curated",
                "shuffled_skill_view": lane == "shuffled",
                "within_env_replay": False,
                "replay_eval": False,
                "learning_max_attempts": 3 if lane == "self_generated" else 1,
                "runtime_artifact_pruning": summary,
            },
        )
        write_json(
            output / "metrics.json",
            {
                "n_reflection_task_workspace_violations": workspace_violations,
                "runtime_artifact_pruning": summary,
            },
        )
        write_json(
            output / "runtime_artifact_pruning_manifest.json",
            {
                **summary,
                "removed_directories": [
                    {
                        "path": f"runs/run/harbor-job/run/task-{index}/agent/opencode/xdg-data",
                        "tree_sha256": "c" * 64,
                        "canonical_trajectory_sha256": "a" * 64,
                        "canonical_session_export_sha256": "b" * 64,
                    }
                    for index in range(count)
                ],
            },
        )
        write_json(
            output / "runs/run/reports/full_report.json",
            {
                "n_tasks_attempted": count,
                "reflection": {"n_task_workspace_violations": workspace_violations},
            },
        )
    return {
        "job_id": job_id,
        "label": label,
        "instance_id": environment,
        "group_id": f"group-{lane}",
        "status": "Succeeded",
        "attempt": attempt,
        "updated_at": f"2026-08-01T00:00:0{attempt}Z",
    }


def test_lane_labels_are_exact_and_reject_foreign_evidence() -> None:
    for lane, label in FINAL.LANE_LABELS.items():
        assert FINAL.lane_from_label(label) == lane
        assert FINAL.lane_from_label(f"{label}-E6") == lane
    assert FINAL.lane_from_label("qwen37max-selfgen-v1-13-E1") is None
    assert FINAL.lane_from_label("qwen37-v1-1-19-self-generated-E7") is None


def test_readiness_selects_one_valid_whole_environment_per_lane(
    tmp_path: Path,
) -> None:
    write_controller(tmp_path)
    jobs = []
    for lane in FINAL.LANES:
        for environment in FINAL.ENVIRONMENTS:
            jobs.append(
                write_export(
                    tmp_path,
                    lane=lane,
                    environment=environment,
                    job_id=f"ap-{lane}-{environment}-a0",
                )
            )
    retry = write_export(
        tmp_path,
        lane="self_generated",
        environment="E1",
        job_id="ap-self-generated-E1-a1",
        attempt=1,
    )
    jobs.append(retry)
    write_json(tmp_path / "watcher/inventory.json", {"jobs": jobs})
    finalizer = make_finalizer(tmp_path)

    ready, reason = finalizer.readiness()

    assert reason is None
    assert ready is not None
    assert len(ready["jobs"]) == 30
    selected = json.loads(ready["selected_inventory"].read_text())
    selected_self_e1 = next(
        row
        for row in selected["jobs"]
        if row["lane"] == "self_generated" and row["instance_id"] == "E1"
    )
    assert selected_self_e1["job_id"] == "ap-self-generated-E1-a1"
    assert len(json.loads(ready["selected_reference_inventory"].read_text())["jobs"]) == 6


def test_invalid_new_retry_falls_back_to_older_valid_export(tmp_path: Path) -> None:
    write_controller(tmp_path)
    jobs = []
    for lane in FINAL.LANES:
        for environment in FINAL.ENVIRONMENTS:
            jobs.append(
                write_export(
                    tmp_path,
                    lane=lane,
                    environment=environment,
                    job_id=f"ap-{lane}-{environment}-a0",
                )
            )
    jobs.append(
        write_export(
            tmp_path,
            lane="self_generated",
            environment="E1",
            job_id="ap-self-generated-E1-bad-a1",
            attempt=1,
            workspace_violations=1,
        )
    )
    write_json(tmp_path / "watcher/inventory.json", {"jobs": jobs})

    ready, reason = make_finalizer(tmp_path).readiness()

    assert reason is None
    selected = next(
        row
        for row in ready["jobs"]
        if row["lane"] == "self_generated" and row["instance_id"] == "E1"
    )
    assert selected["job_id"] == "ap-self_generated-E1-a0"
    candidate_audit = json.loads(
        (tmp_path / "v19-finalizer/candidate_validation.json").read_text()
    )
    bad = next(
        row
        for row in candidate_audit["candidates"]
        if row["job_id"] == "ap-self-generated-E1-bad-a1"
    )
    assert bad["selected"] is False
    assert "reflection workspace policy violation recorded" in bad["validation_errors"]


def test_readiness_waits_without_shrinking_the_30_job_matrix(tmp_path: Path) -> None:
    write_controller(tmp_path)
    write_json(tmp_path / "watcher/inventory.json", {"jobs": []})

    ready, reason = make_finalizer(tmp_path).readiness()

    assert ready is None
    assert reason == "waiting for 30 lane/environment cells; 0 cells require a valid retry"
