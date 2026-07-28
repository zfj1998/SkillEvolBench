from __future__ import annotations
from pathlib import Path
import os
import json

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "board_report.json"


def report():
    return json.loads(OUTPUT.read_text())

class TestProcess:
    def test_label_audit_not_blind(self):
        labels = {row["label"] for row in report()["labels"]}
        assert {"vendor", "independent"} <= labels

    def test_pipeline_derives_decision_from_labeled_sources(self):
        data = report()
        basis = data["decision"]["basis"].lower()
        counts = {
            label: sum(row["label"] == label for row in data["labels"])
            for label in ("vendor", "independent")
        }
        assert "vendor" in basis and "independent" in basis
        assert all(str(count) in basis for count in counts.values())
