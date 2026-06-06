import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "analyze_spec_reorg.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_both_specs(self):
        self.assertIn("spec_v1.md", self.code)
        self.assertIn("spec_v2.md", self.code)

    def test_uses_section_helpers(self):
        self.assertIn("section_index", self.code)
        self.assertIn("reorder_detector", self.code)

    def test_outputs_report_file(self):
        self.assertIn("spec_reorg_report.md", self.code)


if __name__ == "__main__":
    unittest.main()
