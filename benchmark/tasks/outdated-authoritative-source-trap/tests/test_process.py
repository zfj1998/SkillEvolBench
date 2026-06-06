from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_considers_year(self):
        assert "year" in (ROOT / "authority_policy.py").read_text()
    def test_not_blind_authority(self):
        text = (ROOT / "authority_policy.py").read_text()
        assert "2019" not in text
