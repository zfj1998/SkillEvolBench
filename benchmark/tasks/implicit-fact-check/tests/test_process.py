from __future__ import annotations
from pathlib import Path
import json

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

class TestProcess:
    def test_pipeline_iterates_all_citations(self):
        text = (ROOT / "audit_pipeline.py").read_text(encoding="utf-8")
        assert "for citation in load_citations()" in text

    def test_policy_checks_content_when_needed(self):
        if {"misrepresented", "selective"} & set(GT["required_problem_labels"]):
            text = (ROOT / "citation_policy.py").read_text(encoding="utf-8").lower()
            assert "content_match" in text or "article_claim" in text

    def test_policy_checks_unsupported_passages_when_needed(self):
        if "invalid" in GT["required_problem_labels"]:
            text = (ROOT / "citation_policy.py").read_text(encoding="utf-8").lower()
            assert "article_claim" in text or "unsupported" in text or "not found" in text

    def test_policy_checks_caveats_when_needed(self):
        if "selective" in GT["required_problem_labels"]:
            text = (ROOT / "citation_policy.py").read_text(encoding="utf-8").lower()
            assert "caveat" in text or "limitation" in text

    def test_policy_checks_authenticity_when_needed(self):
        if "fake" in GT["required_problem_labels"]:
            text = (ROOT / "citation_policy.py").read_text(encoding="utf-8").lower()
            assert "authenticity" in text and ("doi" in text or "journal" in text)
