
import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
SCRIPT = PROJECT / "convert_excel.py"
OUTPUT_DIR = PROJECT / "output"
EXPECTED = json.loads((PROJECT / "expected_summary.json").read_text(encoding="utf-8"))

def run_conversion():
    if OUTPUT_DIR.exists():
        for p in OUTPUT_DIR.iterdir():
            p.unlink()
    else:
        OUTPUT_DIR.mkdir()
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=str(PROJECT))
    return sorted(p.name for p in OUTPUT_DIR.glob("*.csv"))

class PublicTests(unittest.TestCase):
    def test_public_at_least_one_csv_exists(self):
        csvs = run_conversion()
        self.assertGreaterEqual(len(csvs), 1)

class HiddenTests(unittest.TestCase):
    def test_hidden_three_csvs_exist_one_per_sheet(self):
        csvs = run_conversion()
        self.assertEqual(set(csvs), {"Data.csv", "Reference.csv", "Summary.csv"})

    def test_hidden_summary_contains_computed_values_not_formulas(self):
        run_conversion()
        with (OUTPUT_DIR / "Summary.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertTrue(rows)
        self.assertNotIn("=", rows[0]["total_revenue"])
        for row in rows:
            self.assertAlmostEqual(float(row["total_revenue"]), EXPECTED[row["category"]], places=2)

    def test_hidden_data_row_count_is_100(self):
        run_conversion()
        with (OUTPUT_DIR / "Data.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 100)

    def test_hidden_reference_row_count_is_20(self):
        run_conversion()
        with (OUTPUT_DIR / "Reference.csv").open(encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 20)

    def test_hidden_loss_report_exists(self):
        run_conversion()
        report = OUTPUT_DIR / "loss_report.json"
        self.assertTrue(report.exists())
        payload = json.loads(report.read_text(encoding="utf-8"))
        self.assertIsInstance(payload, list)

if __name__ == "__main__":
    unittest.main()
