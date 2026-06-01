# E4-LS5-T2 — Merge Employee Records by Exact Key

The task files are in `/root/task`.

This is the clean baseline task in the family: two sources use the exact same `employee_id`,
so the hard part is not fuzzy matching but producing a correct merged dataset and a useful
conflict log when fields disagree.

Relevant files:
- `/root/task/merge_employee_records.py`
- `/root/task/exact_join.py`
- `/root/task/conflict_policy.py`
- `/root/task/employees.json`
- `/root/task/salaries.json`
- `/root/task/README.md`

Expected outputs:
- `/root/task/master_employees.csv`
- `/root/task/conflict_log.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/master_employees.csv` and `/root/task/conflict_log.json`.
`master_employees.csv` must contain exactly 100 unique employees joined by the exact `employee_id` key (`E001` through `E100`) with this header: `employee_id,name,dept,manager,location,salary,grade,start_date`. `conflict_log.json` must be an object with `merge_key` (string, `employee_id`), `source_priority` (string), `total_conflicts` (integer), `summary.review_queue_size` (integer), `summary.field_counts` (object keyed by field name), and `conflicts` (array). Each conflict entry must include `employee_id` (string), `field` (string), `employees_value` (string), `salaries_value` (string), `resolved_to` (string), `resolved_by` (string naming the source used by the resolution policy), `merge_key` (string, `employee_id`), and `source_priority` (string). The top-level fields describe the whole merge, and the per-conflict fields make each audit entry self-contained. Do not trim the conflict review queue: log every department conflict discovered by comparing `employees.json` and `salaries.json`.
