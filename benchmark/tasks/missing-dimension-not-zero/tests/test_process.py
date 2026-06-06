from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_missingness_policy_exists(self):
        text = (ROOT / "missingness_policy.py").read_text()
        assert "unavailable" in text or "None" in text
