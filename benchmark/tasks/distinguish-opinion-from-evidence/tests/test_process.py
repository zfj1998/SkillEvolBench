from __future__ import annotations
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_labels_each_source(self):
        text = (ROOT / "classification_pipeline.py").read_text()
        assert "labels.append" in text

    def test_method_aware_policy(self):
        text = (ROOT / "evidence_policy.py").read_text()
        assert "source_type" in text or "method" in text.lower()

    def test_not_numbers_only(self):
        text = (ROOT / "evidence_policy.py").read_text()
        assert "randomized_controlled_trial" in text or "opinion_post" in text
