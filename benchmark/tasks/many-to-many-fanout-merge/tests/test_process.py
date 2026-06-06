from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
BRIDGE = PROJECT / "enrollment_bridge.py"
PROCESS = PROJECT / "process_course_load.py"
SCHEMA = PROJECT / "schema_cleaner.py"


def run():
    bridge = read_text(BRIDGE)
    process = read_text(PROCESS)
    schema = read_text(SCHEMA)
    public = run_checks("public", [
        ("uses_enrollment_bridge", lambda: "student_enrollments" in bridge or (_ for _ in ()).throw(AssertionError("enrollment bridge missing"))),
    ])
    hidden = run_checks("hidden", [
        ("joins_on_course_id", lambda: 'on="course_id"' in bridge or "on='course_id'" in bridge or (_ for _ in ()).throw(AssertionError("course_id join missing"))),
        ("avoids_department_fallback", lambda: "left_on=\"major\"" not in bridge and "department" not in bridge.split("merge", 2)[-1] or (_ for _ in ()).throw(AssertionError("department fanout fallback still present"))),
        ("drops_nonpositive_ids", lambda: '> 0' in schema or (_ for _ in ()).throw(AssertionError("nonpositive-id guard missing"))),
        ("deduplicates_student_course_pairs", lambda: '["student_id", "course_id"]' in schema or "['student_id', 'course_id']" in schema or (_ for _ in ()).throw(AssertionError("student-course dedup missing"))),
        ("reports_intermediate_row_count", lambda: "merged_row_count" in process or (_ for _ in ()).throw(AssertionError("intermediate row count audit missing"))),
    ])
    return emit_report("E3-LS3-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
