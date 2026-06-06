from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "evaluation.json"

def setup_module():
    subprocess.run([sys.executable, "evaluation_pipeline.py"], cwd=ROOT, check=True)

def data():
    return json.loads(OUTPUT.read_text())

class TestProcess:
    def test_discovers_multiple_dimensions_from_sources(self):
        assert len(data()["dimensions"]) >= 5

    def test_dimensions_carry_source_evidence(self):
        for dim in data()["dimensions"]:
            evidence = dim.get("evidence", [])
            assert evidence and all(":" in item for item in evidence)
