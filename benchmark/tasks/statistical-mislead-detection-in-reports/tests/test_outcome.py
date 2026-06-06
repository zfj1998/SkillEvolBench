import re
import runpy
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "report_audit.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "audit_report_changes.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8")


class TestOutcomePublic(unittest.TestCase):
    def test_all_claims_have_entries(self):
        report = run_script()
        self.assertGreaterEqual(len(re.findall(r"## \d+\.", report)), 5)

    def test_assessment_present(self):
        self.assertIn("Assessment:", run_script())


class TestOutcomeHidden(unittest.TestCase):
    def test_misleading_claims_detected(self):
        report = run_script().lower()
        self.assertGreaterEqual(report.count("assessment: misleading"), 3)

    def test_small_base_analysis_mentions_absolute_numbers(self):
        report = run_script().lower()
        self.assertRegex(report, r"100.?400|small-base|absolute")

    def test_sample_size_analysis_mentions_20(self):
        report = run_script().lower()
        self.assertRegex(report, r"20 customers|sample size|n=20")

    def test_accurate_cost_claim_not_flagged(self):
        report = run_script().lower()
        self.assertRegex(report, r"operating costs")
        self.assertRegex(report, r"assessment: accurate")

    def test_inflation_and_window_context_are_called_out(self):
        report = run_script().lower()
        self.assertRegex(report, r"inflation|6%")
        self.assertRegex(report, r"7 days|30-day|30 day")

    def test_competitor_scope_is_called_out(self):
        report = run_script().lower()
        self.assertRegex(report, r"3 selected competitors|selected competitors|industry")


if __name__ == "__main__":
    unittest.main()
