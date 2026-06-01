# E4-LS3-T3 — Merge Three Employee Sources and Report Conflicts

The task files are in `/root/task`.

You are maintaining a profile merge step that combines HR, Slack, and directory data.
Some fields disagree across sources, and the tool is expected to fill what it can while
surfacing every real conflict with provenance and a recommended resolution.

The starter currently drops part of that conflict surface. Fix it in place.

Relevant files:
- `/root/task/build_employee_profile.py`
- `/root/task/conflict_policy.py`
- `/root/task/source_adapter.py`
- `/root/task/hr_system.json`
- `/root/task/slack_profile.json`
- `/root/task/company_directory.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/output/employee_profile_report.json` and `/root/output/employee_profile_audit.json`.
The report JSON must contain `profile` and `conflicts`. `profile` includes canonical fields such as `name`, `employee_id`, `department`, `title`, `phone`, `location`, and `email`. Each conflict object must include `field`, `sources`, and `recommended_value`; conflicts for department, phone, and title must be retained. Resolve department by majority source value and do not suppress known conflicts; the audit JSON must include `suppressed_conflicts`.

