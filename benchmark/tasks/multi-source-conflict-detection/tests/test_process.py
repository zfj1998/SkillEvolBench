import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "build_employee_profile.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_reads_all_three_sources(self):
        for name in ["hr_system.json", "slack_profile.json", "company_directory.json"]:
            self.assertIn(name, self.code)
        self.assertIn("conflict_policy", self.code)
        self.assertIn("field_linkage", self.code)

    def test_conflict_structure_present(self):
        self.assertIn("conflicts", self.code)
        self.assertIn("recommended_value", self.code)
        self.assertIn("employee_profile_audit.json", self.code)

    def test_no_hardcoded_winner(self):
        for token in ["Marketing", "Sales", "555-0101", "555-0202"]:
            self.assertNotIn(token, self.code)

if __name__ == "__main__":
    unittest.main()
