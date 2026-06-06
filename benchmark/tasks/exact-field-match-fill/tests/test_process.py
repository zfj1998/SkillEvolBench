import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "fill_employee_form.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_reads_source_file(self):
        self.assertIn("hr_data.md", self.code)
        self.assertIn("read_text", self.code)
        self.assertIn("field_contract", self.code)

    def test_no_employee_value_hardcoding(self):
        banned = ["Alice Chen", "EMP-1042", "Platform Engineering", "Victor Alvarez"]
        for token in banned:
            self.assertNotIn(token, self.code, f"Do not hardcode source value: {token}")

    def test_keeps_output_schema(self):
        self.assertIn("employee_form_filled.json", self.code)
        self.assertIn("template.json", self.code)
        self.assertIn("employee_form_audit.json", self.code)

if __name__ == "__main__":
    unittest.main()
