
import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
SCRIPT = PROJECT / "convert_docx.py"
OUTPUT_MD = PROJECT / "document.md"
OUTPUT_LOSS = PROJECT / "loss_report.json"

def run_conversion():
    if OUTPUT_MD.exists(): OUTPUT_MD.unlink()
    if OUTPUT_LOSS.exists(): OUTPUT_LOSS.unlink()
    subprocess.run([sys.executable, str(SCRIPT)], check=True, cwd=str(PROJECT))
    assert OUTPUT_MD.exists()
    assert OUTPUT_LOSS.exists()
    md = OUTPUT_MD.read_text(encoding="utf-8")
    loss = json.loads(OUTPUT_LOSS.read_text(encoding="utf-8"))
    return md, loss

class PublicTests(unittest.TestCase):
    def test_public_markdown_file_exists_and_nonempty(self):
        md, _ = run_conversion()
        self.assertTrue(md.strip())

    def test_public_loss_report_exists(self):
        _, loss = run_conversion()
        self.assertIsInstance(loss, list)

class HiddenTests(unittest.TestCase):
    def test_hidden_markdown_contains_key_text(self):
        md, _ = run_conversion()
        self.assertIn("Migration Design Notes", md)
        self.assertIn("legacy", md)
        self.assertIn("critical risks", md)

    def test_hidden_loss_report_lists_at_least_three_types(self):
        _, loss = run_conversion()
        types = {item["element_type"] for item in loss}
        self.assertGreaterEqual(len(types), 3)

    def test_hidden_merged_table_is_reported(self):
        _, loss = run_conversion()
        joined = json.dumps(loss).lower()
        self.assertIn("merged_table_cell", joined)

    def test_hidden_footnotes_are_reported(self):
        _, loss = run_conversion()
        joined = json.dumps(loss).lower()
        self.assertIn("footnote", joined)

    def test_hidden_textbox_is_reported(self):
        _, loss = run_conversion()
        joined = json.dumps(loss).lower()
        self.assertIn("textbox", joined)

    def test_hidden_highlight_is_reported(self):
        _, loss = run_conversion()
        joined = json.dumps(loss).lower()
        self.assertIn("highlight", joined)

    def test_hidden_bold_is_not_false_positive(self):
        _, loss = run_conversion()
        joined = json.dumps(loss).lower()
        self.assertNotIn('"bold"', joined)

if __name__ == "__main__":
    unittest.main()
