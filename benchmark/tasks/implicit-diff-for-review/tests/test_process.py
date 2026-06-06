import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "review_updated_spec.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_both_versions(self):
        self.assertIn("onboarding_spec_v1.md", self.code)
        self.assertIn("onboarding_spec_v2.md", self.code)

    def test_uses_diff_summary_helper(self):
        self.assertIn("diff_summary", self.code)


if __name__ == "__main__":
    unittest.main()
