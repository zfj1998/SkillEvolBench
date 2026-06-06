from __future__ import annotations
import json
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_realistic_calendar_files_exist(self):
        assert (PROJECT_ROOT / "calendar" / "participants.json").exists(), "missing participant calendar JSON"
        assert (PROJECT_ROOT / "calendar" / "ics").exists(), "missing ICS export directory"
        ics_files = list((PROJECT_ROOT / "calendar" / "ics").glob("*.ics"))
        assert len(ics_files) >= GT["min_participant_count"], "not enough ICS calendar files"

    def test_pipeline_uses_policy_module(self):
        scheduler = (PROJECT_ROOT / "scheduler.py").read_text(encoding="utf-8")
        assert "scheduling_policy.recommend_schedule" in scheduler, "scheduler should call scheduling policy"

    def test_process_markers(self):
        combined = "\n".join(
            path.read_text(encoding="utf-8", errors="ignore")
            for path in [PROJECT_ROOT / "scheduling_policy.py", PROJECT_ROOT / "calendar_loader.py"]
            if path.exists()
        ).lower()
        for marker in GT.get("process_markers", []):
            assert marker.lower() in combined, f"expected process marker {marker!r}"

    def test_request_context_exists(self):
        assert (PROJECT_ROOT / "scheduling_request.json").exists(), "missing structured scheduling request"
        assert (PROJECT_ROOT / "scheduling_request.md").exists(), "missing human-readable scheduling request"

    def test_no_static_output_in_environment(self):
        assert not (PROJECT_ROOT / "output" / "schedule.json").exists() or (PROJECT_ROOT / "scheduler.py").exists(), "schedule should be produced by pipeline"
