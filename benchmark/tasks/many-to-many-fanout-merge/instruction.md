# Task: Calculate Average Course Load Per Student

The task files are in `/root/task`.

An analyst wants the average number of courses per student, but the current join path is inflating the counts. The input files contain schema noise, so inspect the columns before changing the merge logic.

What to do:
1. Inspect `students.csv`, `enrollments.csv`, and `courses.csv`.
2. Fix the join pipeline so course load is calculated through the proper enrollment bridge.
3. Save the summary to `output.json`.

Make the fix in place under `/root/task`. Do not replace the project with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `average_courses_per_student` (number).
- `max_courses_per_student` (integer).
- `merged_row_count` (integer): row count after joining through the enrollment bridge without fanout.
- `student_course_counts` (array of objects): each object has `student_id` and `course_count`.

Design contract: join students to enrollments to courses on `course_id`; do not fall back to department-name joins. Drop non-positive or invalid IDs, deduplicate repeated student-course pairs, and compute course counts per student from the bridge table.

