from __future__ import annotations
import json
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_pipeline_checks_candidate_pairs(self):
        text = (ROOT / "audit_pipeline.py").read_text(encoding="utf-8")
        assert "for pair in graph" in text

    def test_scope_normalizer_uses_time_and_scope(self):
        if GT["false_ids"]:
            text = (ROOT / "scope_normalizer.py").read_text(encoding="utf-8").lower()
            assert "period" in text and "scope" in text

    def test_policy_supports_required_types(self):
        text = (ROOT / "contradiction_policy.py").read_text(encoding="utf-8").lower()
        for required in GT["required_types"]:
            assert required.lower() in text

    def test_pipeline_uses_grounding_files(self):
        text = (ROOT / "audit_pipeline.py").read_text(encoding="utf-8").lower()
        assert "source_cards.md" in text
        assert "source_url_index.json" in text
        assert "evidence_index.json" in text

