import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "audit_report_changes.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_both_versions(self):
        self.assertIn("report_draft.md", self.code)
        self.assertIn("report_published.md", self.code)

    def test_uses_claim_registry(self):
        self.assertIn("claim_registry", self.code)
        self.assertIn("extract_claims", self.code)
        self.assertIn("context_evidence", self.code)

    def test_has_semantic_assessment_step(self):
        self.assertIn("semantic_checks", self.code)
        self.assertIn("assessment, analysis =", self.code)


if __name__ == "__main__":
    unittest.main()
