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
