import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "extract_latest_revenue.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_report_document(self):
        self.assertIn("annual_report.md", self.code)

    def test_uses_reference_and_table_helpers(self):
        self.assertIn("reference_resolver", self.code)
        self.assertIn("table_validator", self.code)


if __name__ == "__main__":
    unittest.main()
