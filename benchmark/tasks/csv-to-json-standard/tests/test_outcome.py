
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
SCRIPT = PROJECT / "convert_csv.py"
OUTPUT = PROJECT / "output.json"

def run_conversion():
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=str(PROJECT))
    assert OUTPUT.exists(), "output.json was not created"
    return json.loads(OUTPUT.read_text(encoding="utf-8"))

class PublicTests(unittest.TestCase):
    def test_public_row_count_is_100(self):
        data = run_conversion()
        self.assertEqual(len(data), 100)

    def test_public_every_row_has_5_fields(self):
        data = run_conversion()
        for row in data:
            self.assertEqual(set(row), {"id", "name", "date", "amount", "category"})

class HiddenTests(unittest.TestCase):
    def test_hidden_preserve_leading_zero_id_as_string(self):
        data = run_conversion()
        row = data[6]
        self.assertEqual(row["id"], "007")
        self.assertIsInstance(row["id"], str)

    def test_hidden_parse_thousands_amount_as_number(self):
        data = run_conversion()
        row = data[6]
        self.assertEqual(row["amount"], 1222.56)
        self.assertIsInstance(row["amount"], float)

    def test_hidden_keep_date_as_string(self):
        data = run_conversion()
        self.assertIsInstance(data[12]["date"], str)
        self.assertEqual(data[12]["date"], "2024-01-13")

    def test_hidden_all_rows_were_converted(self):
        data = run_conversion()
        self.assertEqual(data[-1]["name"], "Customer 099")

if __name__ == "__main__":
    unittest.main()
