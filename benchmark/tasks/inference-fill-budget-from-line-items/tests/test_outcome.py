import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "project_report_filled.json"
EVIDENCE = ROOT / "output" / "budget_evidence.json"

def run_script(script: Path):
    runpy.run_path(str(script), run_name="__main__")

class TestOutcomePublic(unittest.TestCase):
    def setUp(self):
        outdir = ROOT / "output"
        if outdir.exists():
            shutil.rmtree(outdir)

    def test_report_generated_and_filled(self):
        run_script(PROJECT / "fill_project_report.py")
        data = json.loads(OUTPUT.read_text())
        self.assertTrue(data["project_name"])
        self.assertTrue(data["total_budget"])

class TestOutcomeHidden(unittest.TestCase):
    def test_total_budget_is_correct(self):
        run_script(PROJECT / "fill_project_report.py")
        data = json.loads(OUTPUT.read_text())
        self.assertEqual(data["total_budget"], "$77,000")

    def test_breakdown_includes_footnote_items(self):
        run_script(PROJECT / "fill_project_report.py")
        items = {x["item"]: x["amount"] for x in json.loads(OUTPUT.read_text())["budget_breakdown"]}
        self.assertIn("Contingency", items)
        self.assertIn("Overhead", items)

    def test_breakdown_includes_appendix_item(self):
        run_script(PROJECT / "fill_project_report.py")
        items = {x["item"]: x["amount"] for x in json.loads(OUTPUT.read_text())["budget_breakdown"]}
        self.assertIn("Miscellaneous support materials", items)

    def test_budget_evidence_schema_and_sources(self):
        run_script(PROJECT / "fill_project_report.py")
        plan_text = (PROJECT / "project_plan.md").read_text()
        evidence = json.loads(EVIDENCE.read_text())
        items = evidence["items"] if isinstance(evidence, dict) else evidence
        self.assertTrue(items)
        for item in items:
            self.assertIn("item", item)
            self.assertIn("amount", item)
            self.assertIn("source", item)
            self.assertTrue(str(item["source"]).strip())
            self.assertNotEqual(str(item["source"]).strip().lower(), "document")
            self.assertIn(str(item["source"]).strip(), plan_text)

    def test_other_direct_fields_are_correct(self):
        run_script(PROJECT / "fill_project_report.py")
        data = json.loads(OUTPUT.read_text())
        self.assertEqual(data["project_name"], "Helios Upgrade")
        self.assertEqual(data["sponsor"], "Northwind Foundation")
        self.assertEqual(data["report_owner"], "Maya Thompson")
        self.assertEqual(data["start_date"], "2025-02-10")

    def test_generalizes_to_modified_amounts(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(PROJECT, td / "project")
            plan = (td / "project" / "project_plan.md").read_text()
            plan = plan.replace("$30,000", "$31,500").replace("$2,000", "$2,500").replace("$10,000", "$9,000")
            (td / "project" / "project_plan.md").write_text(plan)
            run_script(td / "project" / "fill_project_report.py")
            data = json.loads((td / "output" / "project_report_filled.json").read_text())
            self.assertEqual(data["total_budget"], "$78,000")
            items = {x["item"]: x["amount"] for x in data["budget_breakdown"]}
            self.assertEqual(items["Personnel"], 31500)
            self.assertEqual(items["Miscellaneous support materials"], 2500)
            self.assertEqual(items["Overhead"], 9000)

if __name__ == "__main__":
    unittest.main()
