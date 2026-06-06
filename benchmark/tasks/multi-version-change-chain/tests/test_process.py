import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "analyze_policy_history.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_all_three_versions(self):
        self.assertIn("policy_v1.md", self.code)
        self.assertIn("policy_v2.md", self.code)
        self.assertIn("policy_v3.md", self.code)

    def test_uses_history_helpers(self):
        self.assertIn("version_diff", self.code)
        self.assertIn("rollback_detector", self.code)

    def test_reports_rounds_and_net_changes(self):
        self.assertIn("v1 -> v2", self.code)
        self.assertIn("Net v1 -> v3 changes", self.code)


if __name__ == "__main__":
    unittest.main()
