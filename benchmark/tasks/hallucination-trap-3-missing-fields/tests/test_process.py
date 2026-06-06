import ast
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "project" / "fill_patient_form.py"

class TestProcess(unittest.TestCase):
    def setUp(self):
        self.code = SCRIPT.read_text()
        self.tree = ast.parse(self.code)

    def test_reads_admission_record(self):
        self.assertIn("admission_record.txt", self.code)
        self.assertIn("missing_policy", self.code)

    def test_no_guessing_tokens(self):
        for token in ["Jamie", "O+", "None known"]:
            self.assertNotIn(token, self.code)

    def test_missing_marker_present(self):
        self.assertTrue(any(marker in self.code for marker in ["N/A", "null", "TODO"]) or "missing_policy" in self.code)

if __name__ == "__main__":
    unittest.main()
