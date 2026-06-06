from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "classification.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text())

def setup_module():
    subprocess.run([sys.executable, "classification_pipeline.py"], cwd=ROOT, check=True)

def labels_map():
    data = json.loads(OUTPUT.read_text())
    return {item["source_id"]: item["label"] for item in data["labels"]}

class TestOutcome:
    def test_has_labels_for_all(self):
        assert len(labels_map()) == len(GT["labels"])

    def test_prioritizes_evidence(self):
        data = json.loads(OUTPUT.read_text())
        assert len(data["selected_priority"]) >= 5

    def test_classification_accuracy(self):
        pred = labels_map()
        correct = sum(1 for key, val in GT["labels"].items() if pred.get(key) == val)
        assert correct >= 10

    def test_pseudo_evidence_not_promoted(self):
        pred = labels_map()
        assert pred["R12"] == "opinion"
