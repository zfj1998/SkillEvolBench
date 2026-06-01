from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from enrollment_bridge import attach_course_metadata, summarize_course_load
from schema_cleaner import clean_courses, clean_enrollments, clean_students

STUDENTS_PATH = Path("students.csv")
ENROLLMENTS_PATH = Path("enrollments.csv")
COURSES_PATH = Path("courses.csv")
OUTPUT_PATH = Path("output.json")


def run(
    students_path: Path = STUDENTS_PATH,
    enrollments_path: Path = ENROLLMENTS_PATH,
    courses_path: Path = COURSES_PATH,
    output_path: Path = OUTPUT_PATH,
) -> dict:
    students = clean_students(pd.read_csv(students_path))
    enrollments = clean_enrollments(pd.read_csv(enrollments_path))
    courses = clean_courses(pd.read_csv(courses_path))
    student_courses = attach_course_metadata(students, enrollments, courses)
    course_counts = summarize_course_load(student_courses)
    payload = {
        "average_courses_per_student": round(float(course_counts["course_count"].mean()), 4),
        "max_courses_per_student": int(course_counts["course_count"].max()),
        "merged_row_count": int(len(student_courses)),
        "student_course_counts": course_counts.sort_values("student_id", kind="mergesort").to_dict(orient="records"),
    }
    output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return payload


if __name__ == "__main__":
    run()
