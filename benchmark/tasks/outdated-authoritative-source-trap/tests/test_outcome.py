from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "investment_estimate.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())
def setup_module():
    subprocess.run([sys.executable, "investment_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_output(self):
        assert OUTPUT.exists()
    def test_not_old_primary(self):
        data = json.loads(OUTPUT.read_text())
        assert data["selected_source"] in GT["fresh_ids"]
    def test_mentions_outdated_source_issue(self):
        text = json.loads(OUTPUT.read_text())["rationale"].lower()
        assert "2019" in text or "current" in text or "avoided" in text

    def test_estimate_field_present(self):
        data = json.loads(OUTPUT.read_text())
        assert isinstance(data.get("estimate"), str) and data["estimate"].strip()
