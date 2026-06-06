from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_uses_year(self):
        assert "year" in (ROOT / "authority_policy.py").read_text()
    def test_filters_domain(self):
        assert "ai_chip_market" in (ROOT / "market_pipeline.py").read_text()
    def test_not_authority_only(self):
        text = (ROOT / "authority_policy.py").read_text()
        assert "2019" not in text
