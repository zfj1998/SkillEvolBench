import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "build_comprehensive_summary.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_reads_all_sources(self):
        for name in ["source_hr.json", "source_directory.json", "source_slack.json"]:
            self.assertIn(name, self.code)
        self.assertIn("compensation_policy", self.code)
        self.assertIn("title_policy", self.code)

    def test_no_hardcoded_total_or_recommendation(self):
        for token in ["135000", "Operations", "Customer Success", "555-2001", "555-2009"]:
            self.assertNotIn(token, self.code)

    def test_outputs_conflicts_missing_and_validation(self):
        for token in ["conflicts", "missing_fields", "validation"]:
            self.assertIn(token, self.code)
        self.assertIn("department_title_alignment", self.code)

if __name__ == "__main__":
    unittest.main()
