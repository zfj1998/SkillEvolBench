import json
import re
import runpy
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / "project"
OUTPUT = ROOT / "output" / "employee_form_filled.json"
AUDIT = ROOT / "output" / "employee_form_audit.json"

EXPECTED_KEYS = ["name", "id", "department", "start_date", "salary", "manager", "office"]

def run_script(script_path: Path):
    runpy.run_path(str(script_path), run_name="__main__")

class TestOutcomePublic(unittest.TestCase):
    def setUp(self):
        outdir = ROOT / "output"
        if outdir.exists():
            shutil.rmtree(outdir)

    def test_all_fields_non_empty(self):
        run_script(PROJECT / "fill_employee_form.py")
        data = json.loads(OUTPUT.read_text())
        for key in EXPECTED_KEYS:
            self.assertTrue(str(data.get(key, "")).strip(), f"{key} should not be empty")

    def test_name_correct(self):
        run_script(PROJECT / "fill_employee_form.py")
        data = json.loads(OUTPUT.read_text())
        self.assertEqual(data["name"], "Alice Chen")

class TestOutcomeHidden(unittest.TestCase):
    def test_exact_match_all_fields(self):
        run_script(PROJECT / "fill_employee_form.py")
        data = json.loads(OUTPUT.read_text())
        expected = {
            "name": "Alice Chen",
            "id": "EMP-1042",
            "department": "Platform Engineering",
            "start_date": "2024-03-18",
            "salary": "125000",
            "manager": "Victor Alvarez",
            "office": "Seattle HQ - 14F",
        }
        self.assertEqual(data, expected)

    def test_date_format(self):
        run_script(PROJECT / "fill_employee_form.py")
        data = json.loads(OUTPUT.read_text())
        self.assertRegex(data["start_date"], r"^\d{4}-\d{2}-\d{2}$")

    def test_no_extra_fields(self):
        run_script(PROJECT / "fill_employee_form.py")
        data = json.loads(OUTPUT.read_text())
        self.assertEqual(set(data.keys()), set(EXPECTED_KEYS))

    def test_audit_records_resolved_labels(self):
        run_script(PROJECT / "fill_employee_form.py")
        audit = json.loads(AUDIT.read_text())
        self.assertEqual(set(audit["resolved_labels"].keys()), set(EXPECTED_KEYS))
        self.assertIn(audit["resolved_labels"]["start_date"], {"Start Date", "Start_Date"})

    def test_generalizes_to_variant_source(self):
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            shutil.copytree(PROJECT, td / "project")
            (td / "project" / "hr_data.md").write_text(
                "# HR Export\n\n"
                "Name: Jordan Lee\n"
                "ID: EMP-2009\n"
                "Department: Applied Research\n"
                "Start_Date: 2025-01-06\n"
                "Salary: 148500\n"
                "Manager: Nina Patel\n"
                "Office: New York - 22B\n"
            )
            script = td / "project" / "fill_employee_form.py"
            runpy.run_path(str(script), run_name="__main__")
            out = json.loads((td / "output" / "employee_form_filled.json").read_text())
            self.assertEqual(out["name"], "Jordan Lee")
            self.assertEqual(out["start_date"], "2025-01-06")
            self.assertEqual(out["salary"], "148500")
            self.assertEqual(set(out.keys()), set(EXPECTED_KEYS))
            audit = json.loads((td / "output" / "employee_form_audit.json").read_text())
            self.assertEqual(audit["resolved_labels"]["start_date"], "Start_Date")

if __name__ == "__main__":
    unittest.main()
