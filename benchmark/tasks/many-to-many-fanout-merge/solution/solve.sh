#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "schema_cleaner.py": dedent(
        """
        from __future__ import annotations

        import re

        import pandas as pd


        def _clean_string(value: object) -> str:
            cleaned = str(value).replace("\\ufeff", "").replace("\\u200b", "").replace("\\u200c", "").replace("\\u200d", "")
            cleaned = re.sub(r"\\s+", " ", cleaned).strip()
            return cleaned


        def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
            cleaned = df.copy()
            cleaned.columns = [_clean_string(column).lower().replace(" ", "_") for column in cleaned.columns]
            return cleaned


        def clean_students(df: pd.DataFrame) -> pd.DataFrame:
            cleaned = _clean_columns(df)
            cleaned["student_id"] = pd.to_numeric(cleaned["student_id"].map(_clean_string), errors="coerce")
            cleaned = cleaned.dropna(subset=["student_id"]).copy()
            cleaned = cleaned[cleaned["student_id"] > 0].copy()
            cleaned["student_id"] = cleaned["student_id"].astype(int)
            cleaned["name"] = cleaned["name"].map(_clean_string)
            major_map = {"cs": "computer science"}
            cleaned["major"] = cleaned["major"].map(lambda value: major_map.get(_clean_string(value).lower(), _clean_string(value).lower()))
            return cleaned.drop_duplicates(subset=["student_id"], keep="first").copy()


        def clean_enrollments(df: pd.DataFrame) -> pd.DataFrame:
            cleaned = _clean_columns(df)
            cleaned["student_id"] = pd.to_numeric(cleaned["student_id"].map(_clean_string), errors="coerce")
            cleaned["course_id"] = pd.to_numeric(cleaned["course_id"].map(_clean_string), errors="coerce")
            cleaned = cleaned.dropna(subset=["student_id", "course_id"]).copy()
            cleaned = cleaned[(cleaned["student_id"] > 0) & (cleaned["course_id"] > 0)].copy()
            cleaned["student_id"] = cleaned["student_id"].astype(int)
            cleaned["course_id"] = cleaned["course_id"].astype(int)
            cleaned["semester"] = cleaned["semester"].map(_clean_string)
            cleaned["grade"] = cleaned["grade"].map(_clean_string)
            return cleaned.drop_duplicates(subset=["student_id", "course_id"], keep="first").copy()


        def clean_courses(df: pd.DataFrame) -> pd.DataFrame:
            cleaned = _clean_columns(df)
            cleaned["course_id"] = pd.to_numeric(cleaned["course_id"].map(_clean_string), errors="coerce")
            cleaned = cleaned.dropna(subset=["course_id"]).copy()
            cleaned = cleaned[cleaned["course_id"] > 0].copy()
            cleaned["course_id"] = cleaned["course_id"].astype(int)
            cleaned["course_name"] = cleaned["course_name"].map(_clean_string)
            cleaned = cleaned[cleaned["course_name"].ne("")].copy()
            cleaned["department"] = cleaned["department"].map(lambda value: _clean_string(value).lower())
            cleaned["credits"] = pd.to_numeric(cleaned["credits"].map(_clean_string), errors="coerce").fillna(0).astype(int)
            return cleaned.drop_duplicates(subset=["course_id"], keep="first").copy()
        """
    ),
    "enrollment_bridge.py": dedent(
        """
        from __future__ import annotations

        import pandas as pd


        def attach_course_metadata(
            students: pd.DataFrame,
            enrollments: pd.DataFrame,
            courses: pd.DataFrame,
        ) -> pd.DataFrame:
            student_enrollments = students.merge(enrollments, on="student_id", how="left", validate="1:m")
            return student_enrollments.merge(courses, on="course_id", how="left", validate="m:1")


        def summarize_course_load(student_courses: pd.DataFrame) -> pd.DataFrame:
            counts = (
                student_courses.dropna(subset=["course_name"])
                .groupby("student_id", as_index=False)
                .size()
                .rename(columns={"size": "course_count"})
            )
            return counts
        """
    ),
    "process_course_load.py": dedent(
        """
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
            valid_rows = student_courses["course_name"].notna().sum()
            payload = {
                "average_courses_per_student": round(float(course_counts["course_count"].mean()), 4),
                "max_courses_per_student": int(course_counts["course_count"].max()),
                "merged_row_count": int(valid_rows),
                "student_course_counts": course_counts.sort_values("student_id", kind="mergesort").to_dict(orient="records"),
            }
            output_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            return payload


        if __name__ == "__main__":
            run()
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
