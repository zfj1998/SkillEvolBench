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
    persisted = json.loads(state_path.read_text(encoding="utf-8"))
    assert persisted["fable_e4_repair"] == repair
    assert set(persisted["stages"]) == set(MATRIX.STAGE_NAMES)
    assert persisted["stages"]["fable_curated_all"]["status"] == "pending"
    assert persisted["stages"]["qwen_curated_all"]["status"] == "pending"


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
    assert watcher.state["stages"]["fable_curated_all"]["group_id"] == (
        "group-curated-all"
    )
