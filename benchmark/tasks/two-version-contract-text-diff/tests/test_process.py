import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "compare_contract_versions.py"


class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text(encoding="utf-8")
        self.tree = ast.parse(self.code)

    def test_reads_both_contract_versions(self):
        self.assertIn("contract_v1.md", self.code)
        self.assertIn("contract_v2.md", self.code)

    def test_uses_helper_modules(self):
        self.assertIn("clause_index", self.code)
        self.assertIn("change_classifier", self.code)
        self.assertIn("split_sections", self.code)

    def test_outputs_structured_report(self):
        self.assertIn("contract_diff_report.md", self.code)
        self.assertIn("lines.append(f\"- type:", self.code)


if __name__ == "__main__":
    unittest.main()
