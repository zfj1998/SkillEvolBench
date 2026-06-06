import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "completed_report.txt"
AUDIT = ROOT / "output" / "placeholder_audit.txt"

def run_script(script: Path):
    runpy.run_path(str(script), run_name="__main__")

class TestOutcomePublic(unittest.TestCase):
    def setUp(self):
        outdir = ROOT / "output"
        if outdir.exists():
            shutil.rmtree(outdir)

    def test_report_exists(self):
        run_script(PROJECT / "complete_report.py")
        self.assertTrue(OUTPUT.exists())

class TestOutcomeHidden(unittest.TestCase):
    def test_all_placeholders_are_filled(self):
        run_script(PROJECT / "complete_report.py")
        content = OUTPUT.read_text()
        for marker in ["[TBD]", "[INSERT HERE]", "___", "<PENDING>"]:
            self.assertNotIn(marker, content)

    def test_filled_values_match_source(self):
        run_script(PROJECT / "complete_report.py")
        content = OUTPUT.read_text()
        for expected in [
            "Region: EMEA",
            "Client: BlueRiver Retail",
            "Launch Date: 2025-05-01",
            "Primary Contact: Theo Kim",
            "Deployment Model: Hybrid",
            "Risk Level: Medium",
            "Next Milestone: Security review",
            "Escalation Lead: Carla Gomez",
        ]:
            self.assertIn(expected, content)

    def test_prefilled_fields_remain_unchanged(self):
        run_script(PROJECT / "complete_report.py")
        content = OUTPUT.read_text()
        self.assertIn("Project: Atlas Rollout", content)
        self.assertIn("Owner: Priya Nair", content)
        self.assertIn("Support Tier: Gold", content)
        self.assertIn("Budget Status: On Track", content)

    def test_placeholder_audit_lists_only_replaced_keys(self):
        run_script(PROJECT / "complete_report.py")
        replaced = set(AUDIT.read_text().splitlines())
        for expected in {"Region", "Client", "Launch Date", "Primary Contact", "Deployment Model", "Risk Level", "Next Milestone", "Escalation Lead"}:
            self.assertIn(expected, replaced)
        for already_filled in {"Project", "Owner", "Support Tier", "Budget Status"}:
            self.assertNotIn(already_filled, replaced)

    def test_generalizes_to_other_placeholder_mix(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(PROJECT, td / "project")
            (td / "project" / "report_template.txt").write_text(
                "Name: [INSERT HERE]\n"
                "Region: <PENDING>\n"
                "Launch Date: ___\n"
                "Status: Ready\n"
            )
            (td / "project" / "data_source.txt").write_text(
                "Name: Solstice Program\nRegion: APAC\nLaunch Date: 2026-01-15\n"
            )
            run_script(td / "project" / "complete_report.py")
            content = (td / "output" / "completed_report.txt").read_text()
            self.assertIn("Name: Solstice Program", content)
            self.assertIn("Region: APAC", content)
            self.assertIn("Launch Date: 2026-01-15", content)
            self.assertIn("Status: Ready", content)

if __name__ == "__main__":
    unittest.main()
