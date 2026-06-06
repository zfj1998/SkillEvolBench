from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_uses_three_dimensions(self):
        text = (ROOT / "dimension_weights.py").read_text()
        assert "relevance" in text and "evidence" in text and "recency" in text
    def test_summary_mentions_dimensions(self):
        assert "dimensions" in (ROOT / "multi_factor_pipeline.py").read_text() or "summary" in (ROOT / "multi_factor_pipeline.py").read_text()
