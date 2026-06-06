from __future__ import annotations
from pathlib import Path
import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_no_top3_truncation(self):
        assert "[:3]" not in (ROOT / "cherry_pick_guard.py").read_text()
