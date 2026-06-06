import re
import runpy
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "contract_diff_report.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "compare_contract_versions.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8")


class TestOutcomePublic(unittest.TestCase):
    def test_change_list_exists(self):
        report = run_script()
        self.assertRegex(report.lower(), r"change 1")

    def test_type_labels_exist(self):
        report = run_script().lower()
        self.assertRegex(report, r"type: (modified|added|deleted)")


class TestOutcomeHidden(unittest.TestCase):
    def test_all_eight_change_groups_present(self):
        report = run_script().lower()
        self.assertEqual(len(re.findall(r"## change \d+", report)), 8)

    def test_amount_changes_show_old_and_new_values(self):
        report = run_script()
        for token in ["$8,000", "$10,500", "30 days", "45 days", "1.5%", "2.0%"]:
            self.assertIn(token, report)

    def test_additions_are_reported(self):
        report = run_script().lower()
        self.assertIn("expense reimbursement", report)
        self.assertIn("dispute resolution", report)

    def test_unchanged_sections_not_flagged(self):
        report = run_script().lower()
        self.assertNotRegex(report, r"section 1: services.*type:")
        self.assertNotRegex(report, r"section 7: warranties.*type:")

    def test_survival_and_liability_changes_are_explicit(self):
        report = run_script().lower()
        self.assertRegex(report, r"three years|survive")
        self.assertRegex(report, r"six .*months|liability cap")


if __name__ == "__main__":
    unittest.main()
