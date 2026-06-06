from __future__ import annotations
import json, subprocess, sys
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "board_report.json"
SOURCES = json.loads((ROOT / "source_manifest.json").read_text())
def setup_module():
    subprocess.run([sys.executable, "board_pipeline.py"], cwd=ROOT, check=True)
class TestOutcome:
    def test_has_report(self):
        assert OUTPUT.exists()
    def test_all_sources_are_labeled_once(self):
        labels = json.loads(OUTPUT.read_text())["labels"]
        assert len(labels) == len(SOURCES)
        assert {item["source_id"] for item in labels} == {source["id"] for source in SOURCES}
    def test_vendor_sources_not_independent(self):
        labels = {item["source_id"]: item["label"] for item in json.loads(OUTPUT.read_text())["labels"]}
        for source in SOURCES:
            if source["source_type"] in {"vendor_doc", "vendor_community"}:
                assert labels[source["id"]] == "vendor"
            if source["source_type"] == "independent_review":
                assert labels[source["id"]] == "independent"
    def test_has_non_absolute_decision(self):
        decision = json.loads(OUTPUT.read_text())["decision"]["basis"].lower()
        assert "independent" in decision or "vendor" in decision or "split" in decision

    def test_decision_basis_uses_evidence_split(self):
        report = json.loads(OUTPUT.read_text())
        labels = {item["source_id"]: item["label"] for item in report["labels"]}
        vendor_count = sum(1 for label in labels.values() if label == "vendor")
        independent_count = sum(1 for label in labels.values() if label == "independent")
        basis = report["decision"]["basis"].lower()
        assert str(vendor_count) in basis
        assert str(independent_count) in basis
        assert "vendor" in basis and "independent" in basis
