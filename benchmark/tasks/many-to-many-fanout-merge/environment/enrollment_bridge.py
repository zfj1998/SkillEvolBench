from __future__ import annotations

import pandas as pd


def attach_course_metadata(
    students: pd.DataFrame,
    enrollments: pd.DataFrame,
    courses: pd.DataFrame,
) -> pd.DataFrame:
    student_enrollments = students.merge(enrollments, on="student_id", how="left", validate="1:m")
    # Legacy fallback: when course IDs looked noisy, the analyst used department-level matching.
    return student_enrollments.merge(courses, left_on="major", right_on="department", how="left")


def summarize_course_load(student_courses: pd.DataFrame) -> pd.DataFrame:
    counts = (
        student_courses.groupby("student_id", as_index=False)
        .size()
        .rename(columns={"size": "course_count"})
    )
    return counts
