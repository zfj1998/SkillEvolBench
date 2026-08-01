from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "full_180_quality_audit" / "watch_missing_controls.py"
SPEC = importlib.util.spec_from_file_location("watch_missing_controls", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCH)


def _watcher(tmp_path: Path, monkeypatch) -> object:
    monkeypatch.setenv("AP_API_KEY", "test-ap-key")
    monkeypatch.setenv("MODEL_API_KEY", "test-model-key")
    monkeypatch.setenv("MODEL_BASE_URL", "https://model.invalid/v1")
    monkeypatch.setenv("MODEL_NAME", "qwen3.7-max")
    monkeypatch.setenv("AP_HEADERS", "stale-routing-header")
    args = argparse.Namespace(
        repo_root=ROOT,
        audit_root=tmp_path,
        cluster="test-cluster",
        ap_cli="ap",
        poll_sec=120,
        once=True,
    )
    watcher = WATCH.Watcher(args)
    assert "AP_HEADERS" not in watcher.environment
    return watcher


def test_commands_cover_full_shuffled_and_all_tier_reference(
    tmp_path: Path, monkeypatch
) -> None:
    watcher = _watcher(tmp_path, monkeypatch)

    shuffled = watcher.command_for("shuffled")
    reference = watcher.command_for("reference")

    assert "--scope" in shuffled and shuffled[shuffled.index("--scope") + 1] == "full"
    assert "--shuffled-skill-view" in shuffled
    assert "--evaluation-only-t4-t6" in shuffled
    assert "--baseline-name" in shuffled
    assert shuffled[shuffled.index("--baseline-name") + 1] == "curated_static"
    assert "--reference-solution-audit" in reference
    assert reference[reference.index("--reference-audit-tiers") + 1] == ("1,2,3,4,5,6")
    assert WATCH.AGENTHUB_REVISION in shuffled
    assert WATCH.AGENTHUB_REVISION in reference
    assert "test-model-key" not in shuffled
    assert "test-ap-key" not in shuffled


def test_template_gate_requires_both_new_parameters(
    tmp_path: Path, monkeypatch
) -> None:
    watcher = _watcher(tmp_path, monkeypatch)

    monkeypatch.setattr(
        watcher,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, "shuffled_skill_view reference_audit_tiers", ""
        ),
    )
    ready, _ = watcher.template_ready()
    assert ready is True

    monkeypatch.setattr(
        watcher,
        "run",
        lambda *args, **kwargs: subprocess.CompletedProcess(
            [], 0, '{"params":{"shuffled_skill_view":{}}}', ""
        ),
    )
    ready, _ = watcher.template_ready()
    assert ready is False


def test_group_id_parser_recovers_nested_submission() -> None:
    assert (
        WATCH.find_group_id({"submission": {"group_id": "group-123-d2"}})
        == "group-123-d2"
    )
