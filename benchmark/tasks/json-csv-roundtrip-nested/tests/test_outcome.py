
import csv
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
SCRIPT = PROJECT / "roundtrip.py"
INPUT = PROJECT / "input.json"
CSV_OUT = PROJECT / "flattened.csv"
ROUNDTRIP_OUT = PROJECT / "roundtrip.json"
VERIFY_OUT = PROJECT / "verification.json"

def run_pipeline():
    for p in [CSV_OUT, ROUNDTRIP_OUT, VERIFY_OUT]:
        if p.exists():
            p.unlink()
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=str(PROJECT))
    original = json.loads(INPUT.read_text(encoding="utf-8"))
    restored = json.loads(ROUNDTRIP_OUT.read_text(encoding="utf-8"))
    verify = json.loads(VERIFY_OUT.read_text(encoding="utf-8"))
    return original, restored, verify

class PublicTests(unittest.TestCase):
    def test_public_roundtrip_json_exists(self):
        _, restored, _ = run_pipeline()
        self.assertIn("user", restored)

class HiddenTests(unittest.TestCase):
    def test_hidden_recursive_roundtrip_matches_exactly(self):
        original, restored, _ = run_pipeline()
        self.assertEqual(restored, original)

    def test_hidden_order_array_length_preserved(self):
        _, restored, _ = run_pipeline()
        self.assertEqual(len(restored["user"]["orders"]), 2)

    def test_hidden_null_is_still_null(self):
        _, restored, _ = run_pipeline()
        self.assertIsNone(restored["user"]["nickname"])
        self.assertIsNone(restored["user"]["orders"][0]["coupon"])

    def test_hidden_bool_fields_stay_bool(self):
        _, restored, _ = run_pipeline()
        self.assertIs(restored["user"]["active"], True)
        self.assertIs(restored["user"]["address"]["verified"], False)

    def test_hidden_flattened_csv_has_dot_path_columns(self):
        run_pipeline()
        with CSV_OUT.open("r", encoding="utf-8", newline="") as f:
            rows = list(csv.DictReader(f))
        self.assertEqual(len(rows), 1)
        self.assertIn("user.address.city", rows[0])
        self.assertIn("user.orders", rows[0])

    def test_hidden_verification_schema_reports_lossless_state(self):
        _, _, verify = run_pipeline()
        self.assertIn("lossless", verify)
        self.assertIn("exact_match", verify)
        self.assertIsInstance(verify["lossless"], bool)
        self.assertIsInstance(verify["exact_match"], bool)
        self.assertIs(verify["lossless"], True)
        self.assertIs(verify["exact_match"], True)

if __name__ == "__main__":
    unittest.main()
