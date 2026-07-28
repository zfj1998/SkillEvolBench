from __future__ import annotations
from pathlib import Path
import os
import json

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "investment_estimate.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())
class TestProcess:
    def test_considers_year(self):
        data = json.loads(OUTPUT.read_text())
        assert data["selected_source"] in GT["fresh_ids"]
    def test_not_blind_authority(self):
        data = json.loads(OUTPUT.read_text())
        assert data["selected_source"] in GT["fresh_ids"]
        assert any(token in data["rationale"].lower() for token in ["2019", "outdated", "current", "fresh"])
