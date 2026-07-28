from __future__ import annotations

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def config() -> dict:
    return load_json(SCRIPT_DIR / "test_config.json")


def output() -> dict:
    return load_json(PROJECT_ROOT / "output" / "thread_actions.json")


def source_count() -> int:
    slack = PROJECT_ROOT / "slack" / "channel_export.json"
    if slack.exists():
        return len(load_json(slack).get("messages", []))
    meeting = PROJECT_ROOT / "meeting" / "paragraphs.json"
    if meeting.exists():
        return len(load_json(meeting).get("paragraphs", []))
    return 0


class TestProcess:
    def test_realistic_source_bundle_exists(self):
        has_slack = (PROJECT_ROOT / "slack" / "channel_export.json").exists() and (PROJECT_ROOT / "slack" / "thread_transcript.md").exists()
        has_meeting = (PROJECT_ROOT / "meeting" / "notes.md").exists() and (PROJECT_ROOT / "meeting" / "paragraphs.json").exists()
        assert has_slack or has_meeting, "expected Slack export or meeting notes source files"
        assert source_count() >= config()["min_source_items"], "source fixture is too small"

    def test_parser_is_modular(self):
        for name in ["thread_parser.py", "context_loader.py", "extraction_policy.py", "summary_writer.py"]:
            assert (PROJECT_ROOT / name).exists(), f"missing parser module {name}"

    def test_all_source_items_processed(self):
        data = output()
        assert data.get("processed_count") == source_count(), "parser must process every source item"
        assert data.get("source_count") == source_count(), "source_count should match fixture size"

    def test_policy_contains_gap_specific_logic(self):
        data = output()
        assert len(data.get("classifications", [])) == source_count()
        assert data.get("actions") and data.get("non_actions"), (
            "policy must distinguish actionable and non-actionable items"
        )

    def test_output_schema_is_complete(self):
        data = output()
        assert isinstance(data.get("actions"), list), "actions list missing"
        assert isinstance(data.get("non_actions"), list), "non_actions list missing"
        assert isinstance(data.get("status_summary"), dict), "status_summary missing"
        assert isinstance(data.get("summary"), dict), "summary missing"
        assert "classifications" in data, "per-source classifications missing"
