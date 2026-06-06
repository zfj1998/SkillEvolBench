import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "complete_report.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_uses_template_and_data_source(self):
        self.assertIn("report_template.txt", self.code)
        self.assertIn("data_source.txt", self.code)
        self.assertIn("placeholder_catalog", self.code)

    def test_no_hardcoded_report_values(self):
        for token in ["BlueRiver Retail", "Theo Kim", "Carla Gomez"]:
            self.assertNotIn(token, self.code)

    def test_handles_multiple_placeholder_styles(self):
        # This is intentionally structural: the fixed solution should reference at least
        # one placeholder token beyond [TBD].
        self.assertTrue(any(marker in self.code for marker in ["[INSERT HERE]", "<PENDING>", "___"]) or "placeholder_catalog" in self.code)

if __name__ == "__main__":
    unittest.main()
