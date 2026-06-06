from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "comparison_summary.json"
def setup_module():
    subprocess.run([sys.executable, "comparison_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_not_only_three_dimensions(self):
        dims = json.loads(OUTPUT.read_text())["dimensions_used"]
        assert len(dims) >= 7
