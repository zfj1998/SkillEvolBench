from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "citation_audit.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([sys.executable, "audit_pipeline.py"], cwd=ROOT, check=True)

def audit():
    return json.loads(OUTPUT.read_text(encoding="utf-8"))

def by_id():
    return {item["citation_id"]: item for item in audit()["results"]}

class TestOutcome:
    def test_output_exists(self):
        assert OUTPUT.exists()

    def test_all_citations_audited(self):
        assert audit()["audited_count"] == len(GT["labels"])

    def test_labels_are_complete(self):
        results = by_id()
        for cid, expected in GT["labels"].items():
            assert results[cid]["label"] == expected, f"{cid} expected {expected}, got {results[cid]['label']}"

    def test_problem_types_detected(self):
        labels = [item["label"] for item in audit()["results"]]
        for label in GT["required_problem_labels"]:
            assert label in labels

    def test_non_fake_problem_types_are_exercised(self):
        labels = {item["label"] for item in audit()["results"]}
        assert {"misrepresented", "selective"}.issubset(labels), labels

    def test_reasons_are_specific(self):
        for cid in GT["problem_ids"]:
            reason = by_id()[cid]["reason"].lower()
            assert any(token in reason for token in GT["reason_terms"][cid]), f"{cid} reason too vague: {reason}"

    def test_valid_items_not_overflagged(self):
        labels = GT["labels"]
        results = by_id()
        valid_ids = [cid for cid, label in labels.items() if label == "valid"]
        correct = sum(1 for cid in valid_ids if results[cid]["label"] == "valid")
        assert correct == len(valid_ids)
