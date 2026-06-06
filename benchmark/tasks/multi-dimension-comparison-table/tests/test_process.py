from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_dimension_registry_exists(self):
        text = (ROOT / "dimension_registry.py").read_text()
        assert "pricing" in text and "security" in text
    def test_more_than_four_dimensions(self):
        text = (ROOT / "dimension_registry.py").read_text()
        assert text.count('"') >= 12
        for dimension in ["pricing", "security", "integrations", "usability", "support", "compliance"]:
            assert dimension in text
