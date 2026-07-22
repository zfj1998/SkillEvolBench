from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/ap/watch_t56_oracle_matrix.py"
SPEC = importlib.util.spec_from_file_location("watch_t56_oracle_matrix", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
MATRIX = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MATRIX)


def test_find_job_id_requires_the_expected_environment() -> None:
    payload = {
        "submission": {
            "jobs": [
                {"job_id": "ap-e3", "instance_id": "E3"},
                {"job_id": "ap-e4", "instance_id": "E4"},
            ]
        }
    }

    assert MATRIX.find_job_id(payload, "E4") == "ap-e4"
    assert MATRIX.find_job_id(payload, "E5") is None


def test_existing_matrix_state_is_migrated_with_durable_e4_repair(
    tmp_path: Path,
    monkeypatch,
) -> None:
    state_dir = tmp_path / "matrix-watcher"
    state_dir.mkdir()
    state_path = state_dir / "state.json"
    state_path.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "stages": {
                    name: {
                        "status": "pending",
                        "idempotency_key": name,
                        "group_id": None,
                    }
                    for name in (
                        "fable_exact_oracle",
                        "fable_no_skill",
                        "qwen_exact_oracle",
                        "qwen_no_skill",
                    )
                },
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        study_root=tmp_path,
        repo_root=ROOT,
        cluster="test-cluster",
        ap_cli="ap",
    )

    watcher = MATRIX.MatrixWatcher(args)

    repair = watcher.state["fable_e4_repair"]
    assert repair["status"] == "pending"
    assert repair["job_id"] is None
    assert repair["idempotency_key"]
    assert repair["failed_jobs"] == []
    assert repair["max_jobs"] == MATRIX.MAX_FABLE_E4_REPAIR_JOBS
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["fable_e4_repair"] == repair
    assert set(persisted["stages"]) == set(MATRIX.STAGE_NAMES)
    assert persisted["stages"]["fable_curated_all"]["status"] == "pending"
    assert persisted["stages"]["qwen_curated_all"]["status"] == "pending"
    assert persisted["stages"]["fable_exact_oracle"]["failed_groups"] == []
    assert persisted["stages"]["fable_exact_oracle"]["max_groups"] == 3


def test_failed_e4_repair_schedules_fresh_job_after_backoff(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        study_root=tmp_path,
        repo_root=ROOT,
        cluster="test-cluster",
        ap_cli="ap",
    )
    watcher = MATRIX.MatrixWatcher(args)
    repair = watcher.state["fable_e4_repair"]
    old_key = repair["idempotency_key"]
    repair.update(
        {
            "status": "submitted",
            "job_id": "ap-failed-e4",
            "registered_with_evidence_watcher": True,
        }
    )
    monkeypatch.setattr(
        watcher,
        "get_job",
        lambda job_id: {"job_id": job_id, "status": "Failed"},
    )

    complete, reason = watcher.advance_e4_repair()

    assert complete is False
    assert "fresh job 2/3 scheduled" in reason
    assert repair["status"] == "retry_backoff"
    assert repair["job_id"] is None
    assert repair["idempotency_key"] != old_key
    assert repair["registered_with_evidence_watcher"] is False
    assert repair["next_submit_attempt_epoch"] > MATRIX.time.time()
    assert repair["failed_jobs"] == [
        {
            "job_id": "ap-failed-e4",
            "status": "Failed",
            "observed_at_utc": repair["failed_jobs"][0]["observed_at_utc"],
            "idempotency_key": old_key,
        }
    ]


def test_e4_repair_stays_active_but_does_not_retry_after_budget(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        study_root=tmp_path,
        repo_root=ROOT,
        cluster="test-cluster",
        ap_cli="ap",
    )
    watcher = MATRIX.MatrixWatcher(args)
    repair = watcher.state["fable_e4_repair"]
    repair.update(
        {
            "status": "submitted",
            "job_id": "ap-failed-3",
            "registered_with_evidence_watcher": True,
            "failed_jobs": [
                {"job_id": "ap-failed-1", "status": "Failed"},
                {"job_id": "ap-failed-2", "status": "Failed"},
            ],
        }
    )
    monkeypatch.setattr(
        watcher,
        "get_job",
        lambda job_id: {"job_id": job_id, "status": "Failed"},
    )

    complete, reason = watcher.advance_e4_repair()

    assert complete is True
    assert "manual review" in reason
    assert repair["status"] == "repair_exhausted"
    assert repair["repair_exhausted"] is True
    assert len(repair["failed_jobs"]) == 3


def test_curated_all_submission_uses_same_content_without_oracle_view(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-ap-key")
    monkeypatch.setenv("ROUTIFY_KEY_sig", "test-only-model-key")
    args = argparse.Namespace(
        study_root=tmp_path,
        repo_root=ROOT,
        cluster="test-cluster",
        ap_cli="ap",
    )
    watcher = MATRIX.MatrixWatcher(args)
    commands: list[list[str]] = []

    def fake_run(command, *, env=None, timeout=300):
        del env, timeout
        commands.append(command)
        return MATRIX.subprocess.CompletedProcess(
            command,
            0,
            json.dumps({"submission": {"group_id": "group-curated-all"}}),
            "",
        )

    monkeypatch.setattr(watcher, "run", fake_run)
    monkeypatch.setattr(watcher, "register_group", lambda *_: None)

    watcher.submit("fable_curated_all")

    command = commands[0]
    assert command[command.index("--baseline-name") + 1] == "curated_static"
    assert "--oracle-skill-view" not in command
    assert "--evaluation-only-t4-t6" in command
    assert command[command.index("--learning-max-attempts") + 1] == "1"
    assert watcher.state["stages"]["fable_curated_all"]["group_id"] == (
        "group-curated-all"
    )


def test_failed_group_is_retried_with_fresh_idempotency_key(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        study_root=tmp_path,
        repo_root=ROOT,
        cluster="test-cluster",
        ap_cli="ap",
    )
    watcher = MATRIX.MatrixWatcher(args)
    stage = watcher.state["stages"]["fable_exact_oracle"]
    old_key = stage["idempotency_key"]
    stage.update(
        {
            "status": "submitted",
            "group_id": "group-failed",
            "registered_with_evidence_watcher": True,
        }
    )
    monkeypatch.setattr(watcher, "register_group", lambda *_: None)
    monkeypatch.setattr(
        watcher,
        "group_jobs",
        lambda group_id: [
            {
                "job_id": f"ap-{index}",
                "instance_id": f"E{index}",
                "status": "Failed",
            }
            for index in range(1, 7)
        ],
    )

    watcher.update_submitted_stages()

    assert stage["status"] == "retry_backoff"
    assert stage["group_id"] is None
    assert stage["idempotency_key"] != old_key
    assert stage["registered_with_evidence_watcher"] is False
    assert stage["next_submit_attempt_epoch"] > MATRIX.time.time()
    assert stage["failed_groups"] == [
        {
            "group_id": "group-failed",
            "job_statuses": {"Failed": 6},
            "observed_at_utc": stage["failed_groups"][0]["observed_at_utc"],
            "idempotency_key": old_key,
        }
    ]
