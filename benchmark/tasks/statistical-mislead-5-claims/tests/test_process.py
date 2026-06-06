from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_reviews_each_claim(self):
        assert "for item in CLAIMS" in (ROOT / "claim_audit.py").read_text()
    def test_not_percentage_only(self):
        text = (ROOT / "claim_audit.py").read_text()
        assert "sample" in text or "inflation" in text or "window" in text
