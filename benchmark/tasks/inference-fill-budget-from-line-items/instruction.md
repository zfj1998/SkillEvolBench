# E4-LS3-T2 — Fill a Report by Reconciling Budget Evidence

The task files are in `/root/task`.

The project-report filler has to infer `total_budget` from line items scattered across
the project plan. The current starter still behaves like an incomplete internal parser:
it collects some sources but misses others.

Fix the workflow so it fills the template correctly and preserves a traceable budget
breakdown.

Relevant files:
- `/root/task/fill_project_report.py`
- `/root/task/budget_sources.py`
- `/root/task/project_plan.md`
- `/root/task/report_template.json`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/output/project_report_filled.json` and `/root/output/budget_evidence.json`.
The filled report must include `project_name`, `sponsor`, `report_owner`, `start_date`, `total_budget`, and `budget_breakdown`. Infer `total_budget` from all line items, including Personnel, Miscellaneous support materials, Overhead, Contingency, and scattered budget text. `budget_breakdown` entries must include `item` and `amount`.

`budget_evidence.json` must be a JSON object with an `items` array. Each evidence item must include `item`, `amount`, and `source`, where `source` names or quotes the source line from `project_plan.md` that produced that budget value.
