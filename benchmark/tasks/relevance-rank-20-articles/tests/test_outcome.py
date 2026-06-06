from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "ranking.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())

def setup_module():
    subprocess.run([sys.executable, "search_pipeline.py"], cwd=ROOT, check=True)

def load_output():
    return json.loads(OUTPUT.read_text())

class TestOutcome:
    def test_has_output(self):
        assert OUTPUT.exists()

    def test_selects_five(self):
        assert len(load_output()["selected"]) == 5

    def test_screens_all_twenty_sources(self):
        assert load_output()["screened"] >= 20

    def test_overlap_with_truth(self):
        selected = [item["source_id"] for item in load_output()["selected"]]
        overlap = len(set(selected) & set(GT["expected_top5"]))
        assert overlap >= 4

    def test_excludes_irrelevant(self):
        selected = [item["source_id"] for item in load_output()["selected"]]
        assert not (set(selected) & set(GT["irrelevant_ids"]))

    def test_reasons_reference_content(self):
        for item in load_output()["selected"]:
            text = item["reason"].lower()
            assert any(key in text for key in ["diagnosis", "validation", "screening", "device", "healthcare", "clinical"])
