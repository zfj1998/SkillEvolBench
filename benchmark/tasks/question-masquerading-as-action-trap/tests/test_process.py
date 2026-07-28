from __future__ import annotations
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_realistic_slack_exports_exist(self):
        assert (PROJECT_ROOT / "slack" / "channel_export.json").exists(), "missing Slack JSON export"
        assert (PROJECT_ROOT / "slack" / "channel_export.ndjson").exists(), "missing Slack ndjson export"
        assert (PROJECT_ROOT / "slack" / "thread_transcript.md").exists(), "missing readable Slack transcript"
        payload = json.loads((PROJECT_ROOT / "slack" / "channel_export.json").read_text(encoding="utf-8"))
        assert len(payload.get("messages", [])) >= GT["min_message_count"], "not enough Slack messages"

    def test_pipeline_uses_policy_modules(self):
        pipeline = (PROJECT_ROOT / "action_tracker.py").read_text(encoding="utf-8")
        assert "extractor_policy.extract_actions" in pipeline, "pipeline must call extraction policy"
        assert "followup_drafter.draft_followups" in pipeline, "pipeline must call follow-up drafter"

    def test_output_schema_fields(self):
        result = json.loads((PROJECT_ROOT / "output" / "actions.json").read_text(encoding="utf-8"))
        assert isinstance(result.get("actions"), list), "actions list required"
        for action in result["actions"]:
            for field in ["id", "source_message_id", "description", "assignee", "status", "confidence", "reason"]:
                assert field in action, f"missing action field {field}"

    def test_current_date_context_when_required(self):
        if not GT.get("requires_current_date"):
            return
        assert (PROJECT_ROOT / "context" / "current_date.json").exists(), "current_date context missing"
