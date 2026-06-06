from __future__ import annotations
import json, subprocess, sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "briefing.md"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())

def setup_module():
    subprocess.run([sys.executable, "briefing_pipeline.py"], cwd=ROOT, check=True)

class TestOutcome:
    def test_has_briefing(self):
        assert OUTPUT.exists()

    def test_excludes_noise(self):
        text = OUTPUT.read_text().lower()
        assert "semiconductor" not in text and "ai index" not in text

    def test_covers_subtopics(self):
        text = OUTPUT.read_text().lower()
        covered = sum(1 for topic in ["solar", "wind", "hydrogen"] if topic in text)
        assert covered >= 2

    def test_has_structure(self):
        text = OUTPUT.read_text()
        assert "## Trends" in text and "## Challenges" in text and "## Outlook" in text
