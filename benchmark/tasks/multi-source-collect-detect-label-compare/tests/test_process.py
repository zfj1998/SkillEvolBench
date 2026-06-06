from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_label_audit_not_blind(self):
        text = (ROOT / "label_audit.py").read_text()
        assert "vendor_doc" in text or "vendor_community" in text

    def test_pipeline_derives_decision_from_labeled_sources(self):
        text = (ROOT / "board_pipeline.py").read_text().lower()
        assert "load_sources" in text
        assert "label_source" in text
        assert "counter" in text or "defaultdict" in text or "for source in sources" in text
        assert "independent" in text and "vendor" in text
