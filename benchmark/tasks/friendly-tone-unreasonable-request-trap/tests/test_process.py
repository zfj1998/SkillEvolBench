from __future__ import annotations
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_realistic_thread_export_exists(self):
        assert (PROJECT_ROOT / "mail" / "raw").exists(), "missing raw .eml exports"
        raw_files = list((PROJECT_ROOT / "mail" / "raw").glob("*.eml"))
        assert len(raw_files) >= GT["min_message_count"], "not enough raw email files"
        assert (PROJECT_ROOT / "mail" / "thread_transcript.md").exists(), "missing readable transcript"

    def test_context_files_available(self):
        assert (PROJECT_ROOT / "context").exists(), "missing context directory"
        assert (PROJECT_ROOT / "task_config.json").exists(), "missing task config"

    def test_pipeline_uses_policy_module(self):
        pipeline = (PROJECT_ROOT / "reply_pipeline.py").read_text(encoding="utf-8")
        assert "reply_policy.select_actions" in pipeline, "pipeline should select reply/ack/ignore actions"
        assert "reply_policy.draft_reply" in pipeline, "pipeline should draft through policy module"

    def test_output_schema_is_structured(self):
        output = json.loads((PROJECT_ROOT / "output" / "replies.json").read_text(encoding="utf-8"))
        assert isinstance(output.get("actions"), list), "actions list required"
        assert isinstance(output.get("replies"), list), "replies list required"
        assert isinstance(output.get("acknowledgements"), list), "acknowledgements list required"
        assert isinstance(output.get("ignored"), list), "ignored list required"
