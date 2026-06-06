import runpy
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "revenue_analysis.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "extract_latest_revenue.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8").lower()


class TestOutcomePublic(unittest.TestCase):
    def test_analysis_exists(self):
        self.assertIn("revenue", run_script())


class TestOutcomeHidden(unittest.TestCase):
    def test_uses_fy2023_total(self):
        report = run_script()
        self.assertIn("118.3", report)

    def test_does_not_label_91_8_as_this_year(self):
        report = run_script()
        self.assertNotRegex(report, r"this year's revenue: \$91\.8m")

    def test_mentions_correct_source_page(self):
        report = run_script()
        self.assertIn("47", report)

    def test_calls_out_incorrect_internal_page_reference(self):
        report = run_script()
        self.assertIn("23", report)
        self.assertRegex(report, r"not the latest|incorrect|points to page 23")


if __name__ == "__main__":
    unittest.main()
