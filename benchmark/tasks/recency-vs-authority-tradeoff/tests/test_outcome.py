from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "market_estimate.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())

def setup_module():
    subprocess.run([sys.executable, "market_pipeline.py"], cwd=ROOT, check=True)

class TestOutcome:
    def test_has_estimate(self):
        assert OUTPUT.exists()
        data = json.loads(OUTPUT.read_text())
        assert isinstance(data.get("estimate"), str) and data["estimate"].strip()

    def test_prefers_current_source(self):
        data = json.loads(OUTPUT.read_text())
        assert data["selected_source"] in GT["acceptable_ids"]

    def test_not_2019_primary(self):
        data = json.loads(OUTPUT.read_text())
        assert data["selected_source"] not in GT["stale_ids"]

    def test_mentions_staleness(self):
        text = json.loads(OUTPUT.read_text())["reasoning"].lower()
        assert "current" in text or "older" in text or "deprioritized" in text
