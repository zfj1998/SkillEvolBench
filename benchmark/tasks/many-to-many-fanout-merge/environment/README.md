# Course Load Analysis

The registrar export contains three tables:

- `students.csv`: one row per student, with noisy headers and a major label.
- `enrollments.csv`: one row per student-course enrollment, with messy `Course_Id` formatting.
- `courses.csv`: course metadata with hidden characters in both headers and values.

The current pipeline falls back to department-level matching when course IDs look unreliable. That creates a many-to-many fanout and inflates the downstream course counts.
