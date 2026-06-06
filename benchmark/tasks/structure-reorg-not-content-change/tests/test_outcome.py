import runpy
import shutil
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "spec_reorg_report.md"


def run_script():
    outdir = ROOT / "output"
    if outdir.exists():
        shutil.rmtree(outdir)
    runpy.run_path(str(PROJECT / "analyze_spec_reorg.py"), run_name="__main__")
    return OUTPUT.read_text(encoding="utf-8").lower()


class TestOutcomePublic(unittest.TestCase):
    def test_report_exists(self):
        self.assertIn("analysis", run_script())


class TestOutcomeHidden(unittest.TestCase):
    def test_reorder_language_present(self):
        report = run_script()
        self.assertRegex(report, r"reorder|reorgan|moved")

    def test_no_content_changes_stated(self):
        report = run_script()
        self.assertRegex(report, r"no content changes|content is identical|zero content changes")

    def test_no_false_deletion_claims(self):
        report = run_script()
        self.assertNotRegex(report, r"removed.*authentication")
        self.assertNotRegex(report, r"deleted.*pagination")

    def test_mapping_present(self):
        report = run_script()
        for token in ["a -> 4", "b -> 5", "c -> 1", "d -> 2", "e -> 3"]:
            self.assertIn(token, report)


if __name__ == "__main__":
    unittest.main()
