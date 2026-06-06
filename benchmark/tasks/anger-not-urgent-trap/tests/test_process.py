from __future__ import annotations
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_realistic_mail_fixture_set_exists(self):
        assert (PROJECT_ROOT / "mail" / "messages.json").exists(), "missing structured mailbox export"
        raw_files = list((PROJECT_ROOT / "mail" / "raw").glob("*.eml"))
        assert len(raw_files) >= GT["min_message_count"], "raw .eml export is incomplete"
        assert (PROJECT_ROOT / "mail" / "mailbox.mbox").exists(), "missing mbox export"

    def test_context_files_are_available(self):
        assert (PROJECT_ROOT / "contacts" / "sender_directory.json").exists(), "missing sender directory"
        assert (PROJECT_ROOT / "contacts" / "org_chart.json").exists(), "missing org chart"
        assert (PROJECT_ROOT / "calendar" / "today.json").exists(), "missing calendar context"

    def test_pipeline_not_static_output_only(self):
        pipeline = (PROJECT_ROOT / "triage_pipeline.py").read_text(encoding="utf-8")
        assert "priority_rules.classify_message" in pipeline, "pipeline should call classification policy"
        assert "output/triage.json" not in (PROJECT_ROOT / "priority_rules.py").read_text(encoding="utf-8"), "policy should not directly write final output"

    def test_reason_and_summary_contract(self):
        output = json.loads((PROJECT_ROOT / "output" / "triage.json").read_text(encoding="utf-8"))
        assert "summary" in output and "counts" in output["summary"], "summary counts required"
        assert all(item.get("reason") for item in output.get("items", [])), "each item needs reason"

    def test_capability_markers_for_advanced_cases(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in [PROJECT_ROOT / "priority_rules.py", PROJECT_ROOT / "context_loader.py", PROJECT_ROOT / "reply_drafter.py"]
            if path.exists()
        ).lower()
        for marker in GT.get("process_markers", []):
            assert marker.lower() in combined, f"expected process marker {marker!r} in policy/pipeline code"
