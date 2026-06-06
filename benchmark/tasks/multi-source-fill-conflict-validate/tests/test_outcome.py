import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "comprehensive_summary.json"
MISSING_MARKERS = {"N/A", "null", "TODO"}

def run_script(script: Path):
    runpy.run_path(str(script), run_name="__main__")

class TestOutcomePublic(unittest.TestCase):
    def setUp(self):
        outdir = ROOT / "output"
        if outdir.exists():
            shutil.rmtree(outdir)

    def test_summary_generated(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        self.assertTrue(OUTPUT.exists())

class TestOutcomeHidden(unittest.TestCase):
    def test_exact_fields_are_filled(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        profile = json.loads(OUTPUT.read_text())["profile"]
        self.assertEqual(profile["employee_name"], "Riley Chen")
        self.assertEqual(profile["employee_id"], "EMP-5510")
        self.assertEqual(profile["manager"], "Sophia Reed")
        self.assertEqual(profile["office"], "Austin")
        self.assertEqual(profile["email"], "riley.chen@example.com")
        self.assertEqual(profile["employment_type"], "Full-time")
        self.assertEqual(profile["slack_handle"], "@rileyc")
        self.assertEqual(profile["title"], "Operations Manager")

    def test_derived_total_compensation_is_correct(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        profile = json.loads(OUTPUT.read_text())["profile"]
        self.assertEqual(profile["total_compensation"], "135000")

    def test_conflicts_are_reported(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        data = json.loads(OUTPUT.read_text())
        fields = {c["field"] for c in data["conflicts"]}
        self.assertEqual(fields, {"department", "title", "phone"})
        dept_conflict = next(c for c in data["conflicts"] if c["field"] == "department")
        self.assertEqual(dept_conflict["recommended_value"], "Operations")
        title_conflict = next(c for c in data["conflicts"] if c["field"] == "title")
        self.assertEqual(title_conflict["recommended_value"], "Operations Manager")

    def test_missing_fields_are_marked(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        data = json.loads(OUTPUT.read_text())
        profile = data["profile"]
        self.assertIn("cost_center", data["missing_fields"])
        self.assertIn("emergency_contact", data["missing_fields"])
        self.assertIn(str(profile["cost_center"]), MISSING_MARKERS)
        self.assertIn(str(profile["emergency_contact"]), MISSING_MARKERS)

    def test_validation_flag_detects_title_department_consistency(self):
        run_script(PROJECT / "build_comprehensive_summary.py")
        validation = json.loads(OUTPUT.read_text())["validation"]
        self.assertTrue(validation["department_title_alignment"])

    def test_generalizes_to_variant_bonus_and_majority(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(PROJECT, td / "project")
            (td / "project" / "source_hr.json").write_text(json.dumps({
                "employee_name": "Riley Chen",
                "employee_id": "EMP-5510",
                "department": "Research",
                "title": "Research Manager",
                "base_salary": 120000,
                "bonus": 20000,
                "manager": "Sophia Reed",
                "office": "Austin",
                "employment_type": "Full-time"
            }, indent=2))
            (td / "project" / "source_directory.json").write_text(json.dumps({
                "employee_name": "Riley Chen",
                "employee_id": "EMP-5510",
                "department": "Research",
                "title": "Research Manager",
                "phone": "555-2001",
                "email": "riley.chen@example.com",
                "office": "Austin"
            }, indent=2))
            run_script(td / "project" / "build_comprehensive_summary.py")
            data = json.loads((td / "output" / "comprehensive_summary.json").read_text())
            self.assertEqual(data["profile"]["total_compensation"], "140000")
            self.assertEqual(data["profile"]["department"], "Research")
            self.assertEqual(data["profile"]["title"], "Research Manager")
            dept_conflict = next(c for c in data["conflicts"] if c["field"] == "department")
            self.assertEqual(dept_conflict["recommended_value"], "Research")

if __name__ == "__main__":
    unittest.main()
