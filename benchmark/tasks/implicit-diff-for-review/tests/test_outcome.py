import runpy
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "updated_spec_review.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "review_updated_spec.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8").lower()


class TestOutcomeHidden(unittest.TestCase):
    def test_at_least_four_content_changes_identified(self):
        report = run_script()
        hits = sum(token in report for token in ["60 days", "swag kit", "14 days", "day 90", "48 hours"])
        self.assertGreaterEqual(hits, 4)

    def test_content_vs_formatting_distinguished(self):
        report = run_script()
        self.assertRegex(report, r"format|metadata")
        self.assertRegex(report, r"content changes")

    def test_no_false_positives_on_unchanged_sections(self):
        report = run_script()
        self.assertNotRegex(report, r"resources.*changed")


if __name__ == "__main__":
    unittest.main()
