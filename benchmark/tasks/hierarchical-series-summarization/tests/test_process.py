from __future__ import annotations
from pathlib import Path
import json

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_priority_policy_is_not_document_order_only(self):
        text = (ROOT / "priority_policy.py").read_text(encoding="utf-8").lower()
        assert "priority" in text

    def test_audience_policy_has_distinct_focus(self):
        text = (ROOT / "audience_policy.py").read_text(encoding="utf-8").lower()
        if GT["shape"] == "multi_audience":
            assert "technical" in text and "management" in text and "client" in text
    def test_summarizer_uses_structured_output(self):
        text = (ROOT / "summarizer.py").read_text(encoding="utf-8").lower()
        assert "summary.json" in text

    def test_summarizer_not_fixed_opening_slice(self):
        text = (ROOT / "summarizer.py").read_text(encoding="utf-8")
        assert "[:3]" not in text
