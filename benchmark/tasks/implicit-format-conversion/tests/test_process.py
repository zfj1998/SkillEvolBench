
import subprocess
import sys
import unittest
from pathlib import Path

PROJECT = Path(__file__).resolve().parents[1] / "project"
OUTPUT = PROJECT / "readable_output.md"


def rendered_text():
    subprocess.run(
        [sys.executable, "make_readable.py"], cwd=PROJECT, check=True
    )
    return OUTPUT.read_text(encoding="utf-8")

class ProcessTests(unittest.TestCase):
    def test_process_not_just_json_code_fence(self):
        text = rendered_text()
        bad = text.lstrip().startswith("```json") and "|" not in text
        self.assertFalse(bad, "expected a true readability transformation, not just pretty-printing")

    def test_process_preserves_data_from_multiple_sections(self):
        text = rendered_text().lower()
        for token in ["company", "teams", "services", "settings", "summary"]:
            self.assertIn(token, text)

if __name__ == "__main__":
    unittest.main()
