import json
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "employee_profile_report.json"
AUDIT_OUTPUT = ROOT / "output" / "employee_profile_audit.json"

def run_script(script: Path):
    runpy.run_path(str(script), run_name="__main__")

class TestOutcomePublic(unittest.TestCase):
    def setUp(self):
        outdir = ROOT / "output"
        if outdir.exists():
            shutil.rmtree(outdir)

    def test_profile_report_is_generated(self):
        run_script(PROJECT / "build_employee_profile.py")
        data = json.loads(OUTPUT.read_text())
        self.assertIn("profile", data)
        self.assertTrue(data["profile"]["name"])
        self.assertTrue(AUDIT_OUTPUT.exists())

class TestOutcomeHidden(unittest.TestCase):
    def test_all_three_conflicts_detected(self):
        run_script(PROJECT / "build_employee_profile.py")
        conflicts = json.loads(OUTPUT.read_text())["conflicts"]
        fields = {c["field"] for c in conflicts}
        self.assertEqual(fields, {"department", "phone", "title"})

    def test_no_linked_conflicts_are_suppressed(self):
        run_script(PROJECT / "build_employee_profile.py")
        audit = json.loads(AUDIT_OUTPUT.read_text())
        self.assertEqual(audit["suppressed_conflicts"], [])

    def test_conflict_entries_include_source_values(self):
        run_script(PROJECT / "build_employee_profile.py")
        conflicts = {c["field"]: c for c in json.loads(OUTPUT.read_text())["conflicts"]}
        self.assertEqual(conflicts["department"]["sources"]["hr_system"], "Marketing")
        self.assertEqual(conflicts["department"]["sources"]["slack_profile"], "Sales")
        self.assertEqual(conflicts["department"]["sources"]["company_directory"], "Marketing")

    def test_non_conflicting_fields_are_filled(self):
        run_script(PROJECT / "build_employee_profile.py")
        profile = json.loads(OUTPUT.read_text())["profile"]
        self.assertEqual(profile["name"], "Dana Brooks")
        self.assertEqual(profile["employee_id"], "E-7781")
        self.assertEqual(profile["location"], "Chicago")
        self.assertEqual(profile["email"], "dana.brooks@example.com")

    def test_department_resolution_uses_majority(self):
        run_script(PROJECT / "build_employee_profile.py")
        data = json.loads(OUTPUT.read_text())
        self.assertEqual(data["profile"]["department"], "Marketing")
        department_conflict = next(c for c in data["conflicts"] if c["field"] == "department")
        self.assertEqual(department_conflict["recommended_value"], "Marketing")

    def test_generalizes_to_modified_majority(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(PROJECT, td / "project")
            (td / "project" / "hr_system.json").write_text(json.dumps({
                "name": "Dana Brooks",
                "employee_id": "E-7781",
                "department": "Research",
                "phone": "555-0101",
                "title": "Research Manager",
                "location": "Chicago"
            }, indent=2))
            (td / "project" / "company_directory.json").write_text(json.dumps({
                "name": "Dana Brooks",
                "employee_id": "E-7781",
                "department": "Research",
                "phone": "555-0202",
                "title": "Research Manager",
                "location": "Chicago",
                "email": "dana.brooks@example.com"
            }, indent=2))
            run_script(td / "project" / "build_employee_profile.py")
            data = json.loads((td / "output" / "employee_profile_report.json").read_text())
            self.assertEqual(data["profile"]["department"], "Research")
            department_conflict = next(c for c in data["conflicts"] if c["field"] == "department")
            self.assertEqual(department_conflict["recommended_value"], "Research")

if __name__ == "__main__":
    unittest.main()
