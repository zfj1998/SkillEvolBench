# E4-LS4-T6 — Analyse a Three-Version Policy History and Identify Rollbacks

The task files are in `/root/task`.

This is the full change-history task: compare `policy_v1.md`, `policy_v2.md`, and
`policy_v3.md`, explain the two round-by-round diffs, identify which v2 edits were
rolled back in v3, and summarise the net v1-to-v3 changes.

The starter was expanded into a small history-analysis pipeline, but it still relies on
position-based section comparison and ends up blurring true rollbacks with section
renumbering. Fix it in place.

Relevant files:
- `/root/task/analyze_policy_history.py`
- `/root/task/version_diff.py`
- `/root/task/rollback_detector.py`
- `/root/task/policy_v1.md`
- `/root/task/policy_v2.md`
- `/root/task/policy_v3.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/policy_history_report.md` (`/root/output/policy_history_report.md` in the default container layout).
The markdown must include sections for `v1 -> v2`, `v2 -> v3`, `Rollbacks`, and `Net v1 -> v3 changes`. Identify at least four v1->v2 changes and at least three v2->v3 changes. Mark eligibility and security changes as rolled back, and list net changes such as co-working stipend and internet reimbursement while excluding rolled-back eligibility and quarterly security briefing changes from the net section.

