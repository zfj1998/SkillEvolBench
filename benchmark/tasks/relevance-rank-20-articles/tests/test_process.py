from __future__ import annotations
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()

class TestProcess:
    def test_scans_manifest(self):
        text = (ROOT / "search_pipeline.py").read_text()
        assert "for source in load_sources()" in text

    def test_not_title_only(self):
        text = (ROOT / "relevance_policy.py").read_text()
        assert "notes" in text or "tier" in text

    def test_not_hardcoded_selection(self):
        text = (ROOT / "search_pipeline.py").read_text()
        assert "[:5]" in text and "expected_top5" not in text
