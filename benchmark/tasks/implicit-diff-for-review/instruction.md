# E4-LS4-T4 — Review the Updated Spec by Inferring the Diff Workflow

The task files are in `/root/task`.

The instruction here is intentionally underspecified: a reviewer asked for a summary of
what changed in the updated onboarding specification. The helper needs to infer that
this requires a v1-vs-v2 comparison rather than a plain summary of the latest file.

Fix the starter so it compares both versions, distinguishes content edits from
formatting-only edits, and writes a focused review report.

Relevant files:
- `/root/task/review_updated_spec.py`
- `/root/task/diff_summary.py`
- `/root/task/onboarding_spec_v1.md`
- `/root/task/onboarding_spec_v2.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/updated_spec_review.md` (`/root/output/updated_spec_review.md` in the default container layout).
The markdown review must identify at least four of the five changes between the two onboarding specs, distinguish content changes from formatting/metadata changes, and avoid claiming unchanged resources changed. It should be based on comparing both v1 and v2 files, not reading only the updated spec.

