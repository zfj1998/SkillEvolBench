# E4-LS3-T6 — Build a Comprehensive Profile from All Available Sources

The task files are in `/root/task`.

This is the most complete version of the family: combine HR, directory, and Slack
exports, fill a summary template, surface conflicts, mark missing values, derive
`total_compensation`, and keep the validation checks meaningful.

The starter currently under-derives one required field. Fix the workflow in place.

Relevant files:
- `/root/task/build_comprehensive_summary.py`
- `/root/task/compensation_policy.py`
- `/root/task/conflict_resolver.py`
- `/root/task/title_policy.py`
- `/root/task/validation_policy.py`
- `/root/task/source_hr.json`
- `/root/task/source_directory.json`
- `/root/task/source_slack.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/output/comprehensive_summary.json`.
The JSON must include `profile`, `conflicts`, `missing_fields`, and `validation`. `profile` includes employee identity, manager, office, email, employment type, slack handle, department, title, phone, compensation fields, `total_compensation`, `cost_center`, and `emergency_contact`. Compute `total_compensation` as salary plus bonus. Conflicts must include department, title, and phone with `recommended_value`; use `title_policy.py` to normalize title variants before recommending the final title. Missing fields must include cost center and emergency contact with explicit missing markers. `validation.department_title_alignment` must be true when the recommended normalized title matches the department.
