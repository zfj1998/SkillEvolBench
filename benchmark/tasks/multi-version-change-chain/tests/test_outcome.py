import runpy
import re
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "policy_history_report.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "analyze_policy_history.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8").lower()


class TestOutcomePublic(unittest.TestCase):
    def test_round_sections_exist(self):
        report = run_script()
        self.assertIn("v1 -> v2", report)
        self.assertIn("v2 -> v3", report)

    def test_rollbacks_section_exists(self):
        self.assertIn("rollbacks", run_script())


class TestOutcomeHidden(unittest.TestCase):
    def test_first_round_changes_are_covered(self):
        report = run_script()
        hits = sum(
            bool(re.search(pattern, report))
            for pattern in [
                r"\b60 days\b",
                r"\b10 am\s*[-\u2013\u2014]\s*4 pm\b",
                r"\$800\b",
                r"\bquarterly security briefings?\b",
                r"\$150(?:/|\s+per\s+)month\b",
            ]
        )
        self.assertGreaterEqual(hits, 4)

    def test_second_round_changes_are_covered(self):
        report = run_script()
        hits = sum(
            token in report
            for token in [
                "march 1, 2024",
                "90 days",
                "$75",
                "semi-annual",
            ]
        )
        self.assertGreaterEqual(hits, 3)

    def test_rollbacks_identified(self):
        report = run_script()
        self.assertRegex(report, r"eligibility.*rolled back|rolled back.*eligibility")
        self.assertRegex(report, r"security.*rolled back|rolled back.*security")

    def test_net_changes_reflect_final_state(self):
        report = run_script()
        self.assertIn("net v1 -> v3 changes", report)
        self.assertIn("co-working stipend", report)
        self.assertIn("internet reimbursement", report)

    def test_rolled_back_items_do_not_appear_as_net_changes(self):
        report = run_script()
        net_section = report.split("## net v1 -> v3 changes", 1)[1]
        self.assertNotRegex(net_section, r"\beligibility\b")
        self.assertNotRegex(net_section, r"quarterly security briefings")


if __name__ == "__main__":
    unittest.main()
