from __future__ import annotations
from pathlib import Path
import os
import json

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
class TestProcess:
    def test_no_top3_truncation(self):
        data = json.loads(
            (ROOT / "output" / "comparison_summary.json").read_text()
        )
        assert len(data["dimensions_used"]) >= 7
