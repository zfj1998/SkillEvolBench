import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "fill_project_report.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_reads_project_plan_document(self):
        self.assertIn("project_plan.md", self.code)
        self.assertIn("read_text", self.code)
        self.assertIn("budget_sources", self.code)

    def test_no_hardcoded_total(self):
        self.assertNotIn("$77,000", self.code)
        self.assertNotIn("77000", self.code)

    def test_uses_breakdown_output(self):
        self.assertIn("budget_breakdown", self.code)
        self.assertIn("total_budget", self.code)
        self.assertIn("budget_evidence.json", self.code)

if __name__ == "__main__":
    unittest.main()
