
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
SCRIPT = PROJECT / "make_readable.py"
INPUT = PROJECT / "data.min.json"
OUTPUT = PROJECT / "readable_output.md"

def run_render():
    if OUTPUT.exists():
        OUTPUT.unlink()
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=str(PROJECT))
    return OUTPUT.read_text(encoding="utf-8"), json.loads(INPUT.read_text(encoding="utf-8"))

class PublicTests(unittest.TestCase):
    def test_public_output_exists(self):
        text, _ = run_render()
        self.assertTrue(text.strip())

class HiddenTests(unittest.TestCase):
    def test_hidden_more_than_raw_pretty_json(self):
        text, _ = run_render()
        self.assertIn("#", text, "expected headings or titled sections")
        self.assertTrue("|" in text or "## Teams" in text, "expected tables or clearly structured sections")

    def test_hidden_key_data_preserved(self):
        text, data = run_render()
        self.assertIn("Northwind Analytics", text)
        self.assertIn("Quarter-end snapshot", text)
        self.assertIn("svc_17", text)
        self.assertIn("flag_159", text)

    def test_hidden_hierarchical_structure_is_clear(self):
        text, _ = run_render()
        for section in ["Company", "Teams", "Services", "Settings", "Summary"]:
            self.assertIn(section.lower(), text.lower())

if __name__ == "__main__":
    unittest.main()
