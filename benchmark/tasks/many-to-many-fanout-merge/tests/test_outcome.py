from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

from verifier_lib.runtime import emit_report, print_report, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_course_load.py"
STUDENTS = PROJECT / "students.csv"
ENROLLMENTS = PROJECT / "enrollments.csv"
COURSES = PROJECT / "courses.csv"
OUTPUT = PROJECT / "output.json"


def _clean_string(value: object) -> str:
    return str(value).replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "").strip()


def _expected():
    students = pd.read_csv(STUDENTS)
    students.columns = [_clean_string(col).lower().replace(" ", "_") for col in students.columns]
    students["student_id"] = pd.to_numeric(students["student_id"].map(_clean_string), errors="coerce")
    students = students.dropna(subset=["student_id"]).copy()
    students = students[students["student_id"] > 0].copy()
    students["student_id"] = students["student_id"].astype(int)
    students = students.drop_duplicates(subset=["student_id"], keep="first").copy()

    enrollments = pd.read_csv(ENROLLMENTS)
    enrollments.columns = [_clean_string(col).lower().replace(" ", "_") for col in enrollments.columns]
    enrollments["student_id"] = pd.to_numeric(enrollments["student_id"].map(_clean_string), errors="coerce")
    enrollments["course_id"] = pd.to_numeric(enrollments["course_id"].map(_clean_string), errors="coerce")
    enrollments = enrollments.dropna(subset=["student_id", "course_id"]).copy()
    enrollments = enrollments[(enrollments["student_id"] > 0) & (enrollments["course_id"] > 0)].copy()
    enrollments["student_id"] = enrollments["student_id"].astype(int)
    enrollments["course_id"] = enrollments["course_id"].astype(int)
    enrollments = enrollments.drop_duplicates(subset=["student_id", "course_id"], keep="first").copy()

    courses = pd.read_csv(COURSES)
    courses.columns = [_clean_string(col).lower().replace(" ", "_") for col in courses.columns]
    courses["course_id"] = pd.to_numeric(courses["course_id"].map(_clean_string), errors="coerce")
    courses = courses.dropna(subset=["course_id"]).copy()
    courses = courses[courses["course_id"] > 0].copy()
    courses["course_id"] = courses["course_id"].astype(int)
    courses["course_name"] = courses["course_name"].map(_clean_string)
    courses = courses[courses["course_name"].ne("")].copy()
    courses = courses.drop_duplicates(subset=["course_id"], keep="first").copy()

    student_courses = students.merge(enrollments, on="student_id", how="left", validate="1:m").merge(courses, on="course_id", how="left", validate="m:1")
    counts = (
        student_courses.dropna(subset=["course_name"])
        .groupby("student_id", as_index=False)
        .size()
        .rename(columns={"size": "course_count"})
    )
    return student_courses, counts


def _run():
    if OUTPUT.exists():
        OUTPUT.unlink()
    result = subprocess.run([sys.executable, str(SCRIPT)], cwd=PROJECT, capture_output=True, text=True, timeout=60)
    payload = json.loads(OUTPUT.read_text(encoding="utf-8")) if OUTPUT.exists() else {}
    return result, payload


def run():
    student_courses, counts = _expected()
    expected_average = float(counts["course_count"].mean())
    public = run_checks("public", [
        ("average_in_expected_range", lambda: 2.0 <= _run()[1].get("average_courses_per_student", 0) <= 6.0 or (_ for _ in ()).throw(AssertionError("average course count implausible"))),
    ])
    hidden = run_checks("hidden", [
        ("average_matches_ground_truth", lambda: abs(_run()[1].get("average_courses_per_student", 0) - expected_average) <= 0.05 or (_ for _ in ()).throw(AssertionError("average course count incorrect"))),
        ("max_courses_reasonable", lambda: _run()[1].get("max_courses_per_student", 999) <= 12 or (_ for _ in ()).throw(AssertionError("fanout inflated per-student counts"))),
        ("merged_row_count_expected", lambda: abs(_run()[1].get("merged_row_count", 0) - int(student_courses["course_name"].notna().sum())) <= 5 or (_ for _ in ()).throw(AssertionError("intermediate row count indicates fanout"))),
        ("no_student_at_500_courses", lambda: max(record["course_count"] for record in _run()[1].get("student_course_counts", [{"course_count": 999}])) < 500 or (_ for _ in ()).throw(AssertionError("student-level fanout detected"))),
    ])
    return emit_report("E3-LS3-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
