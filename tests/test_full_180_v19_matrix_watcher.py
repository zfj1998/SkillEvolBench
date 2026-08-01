from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

import pytest


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "experiments/full_180_quality_audit/watch_v19_matrix.py"
SPEC = importlib.util.spec_from_file_location("watch_full_180_v19_matrix", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCH)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def controller(tmp_path: Path, monkeypatch) -> object:
    monkeypatch.setenv("AP_API_KEY", "test-ap-key-value")
    monkeypatch.setenv("MODEL_API_KEY", "test-model-key-value")
    monkeypatch.setenv("MODEL_BASE_URL", "https://model.invalid/v1")
    monkeypatch.setenv("MODEL_NAME", WATCH.MODEL)
    args = argparse.Namespace(
        repo_root=ROOT,
        audit_root=tmp_path,
        cluster="test-cluster",
        ap_cli="ap",
        poll_sec=10,
        once=True,
    )
    return WATCH.MatrixController(args)


def test_five_lane_commands_pin_one_protocol_and_preserve_no_replay_baseline(
    tmp_path: Path, monkeypatch
) -> None:
    watcher = controller(tmp_path, monkeypatch)

    commands = {lane: watcher.command_for(lane) for lane in WATCH.LANES}

    for command in commands.values():
        assert command[command.index("--split") + 1] == WATCH.DATASET_SPLIT
        assert command[command.index("--agenthub-ref") + 1] == WATCH.AGENTHUB_REVISION
        assert command[command.index("--concurrency") + 1] == "1"
    self_command = commands["self_generated"]
    assert self_command[self_command.index("--learning-max-attempts") + 1] == "3"
    assert "--within-env-replay" not in self_command
    assert "--no-within-env-replay" not in self_command
    assert "--replay-eval" not in self_command
    assert "--no-replay-eval" not in self_command
    assert "--evaluation-only-t4-t6" not in self_command

    assert "--evaluation-only-t4-t6" in commands["no_skill"]
    assert "--oracle-skill-view" in commands["exact_curated"]
    assert "--shuffled-skill-view" in commands["shuffled"]
    assert "--reference-solution-audit" in commands["reference"]
    assert "--harbor-agent" not in commands["reference"]


def test_existing_state_from_another_revision_is_rejected(
    tmp_path: Path, monkeypatch
) -> None:
    state = {
        "schema_version": 2,
        "benchmark_revision": "0" * 40,
        "agenthub_revision": WATCH.AGENTHUB_REVISION,
        "dataset": WATCH.DATASET,
        "dataset_split": WATCH.DATASET_SPLIT,
        "model": WATCH.MODEL,
        "idempotency_keys": {lane: "00000000-0000-4000-8000-000000000000" for lane in WATCH.LANES},
        "group_ids": {lane: None for lane in WATCH.LANES},
    }
    write_json(tmp_path / "matrix-controller/state.json", state)

    with pytest.raises(RuntimeError, match="different protocol version"):
        controller(tmp_path, monkeypatch)


def test_self_e1_safe_export_is_a_fail_closed_protocol_gate(
    tmp_path: Path, monkeypatch
) -> None:
    watcher = controller(tmp_path, monkeypatch)
    job_id = "ap-smoke"
    group_id = "group-smoke"
    destination = tmp_path / "raw/self/E1/ap-smoke"
    output = destination / "artifacts/output"
    summary = {
        "schema_version": 1,
        "policy": "remove-redundant-opencode-xdg-data-after-session-export",
        "manifest": "runtime_artifact_pruning_manifest.json",
        "removed_directory_count": 30,
        "removed_regular_file_count": 30,
        "removed_regular_file_bytes": 300,
        "removed_symlink_count": 0,
    }
    records = [
        {
            "path": f"runs/run/harbor-job/run/task-{index}/agent/opencode/xdg-data",
            "canonical_trajectory_sha256": "a" * 64,
            "canonical_session_export_sha256": "b" * 64,
        }
        for index in range(30)
    ]
    write_json(
        tmp_path / f"watcher/exports/{job_id}.json",
        {
            "completed": True,
            "unsafe": False,
            "scan_summary": {"clean": True},
            "destination": str(destination),
        },
    )
    write_json(destination / "job.json", {"template_commit": WATCH.AGENTHUB_REVISION})
    write_json(
        output / "ap_run_manifest.json",
        {
            "benchmark_revision": WATCH.BENCHMARK_REVISION,
            "environment_id": "E1",
            "canonical": True,
            "baseline_name": "selfgen_in_session_always",
            "learning_max_attempts": 3,
            "evaluation_only_t4_t6": False,
            "within_env_replay": False,
            "replay_eval": False,
            "runtime_artifact_pruning": summary,
        },
    )
    write_json(
        output / "metrics.json",
        {
            "n_task_workspace_violations": 0,
            "n_reflection_task_workspace_violations": 0,
            "runtime_artifact_pruning": summary,
        },
    )
    write_json(
        output / "runtime_artifact_pruning_manifest.json",
        {**summary, "removed_directories": records},
    )
    write_json(output / "runs/run/reports/full_report.json", {"n_tasks_attempted": 30})
    row = {"job_id": job_id, "group_id": group_id}

    passed, reason = watcher.validate_smoke_export(row)

    assert passed is True
    assert reason == "ok"
    validation = json.loads(
        (tmp_path / "matrix-controller/self_e1_smoke_validation.json").read_text()
    )
    assert validation["passed"] is True

    metrics = json.loads((output / "metrics.json").read_text())
    metrics["n_reflection_task_workspace_violations"] = 1
    write_json(output / "metrics.json", metrics)
    passed, reason = watcher.validate_smoke_export(row)
    assert passed is False
    assert "no_workspace_policy_violation" in reason


def test_remaining_lanes_are_held_until_self_e1_smoke_passes(
    tmp_path: Path, monkeypatch
) -> None:
    watcher = controller(tmp_path, monkeypatch)
    watcher.state["group_ids"]["self_generated"] = "group-self"
    watcher.save()
    submitted: list[str] = []
    monkeypatch.setattr(watcher, "template_ready", lambda: (True, "ok"))
    monkeypatch.setattr(watcher, "smoke_step", lambda: (False, "still running"))
    monkeypatch.setattr(watcher, "submit", lambda lane: submitted.append(lane))

    assert watcher.step() is False
    assert submitted == []
