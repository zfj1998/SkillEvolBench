# E4-LS5-T3 — Compare HR and Finance Records Including Nested Fields

The task files are in `/root/task`.

HR and Finance agree on employee identity and top-level metadata, but some employees have
deeper inconsistencies in nested `address` and `compensation` objects. The task is to
produce a complete difference report with precise dotted field paths and grouped context.

Relevant files:
- `/root/task/build_differences_report.py`
- `/root/task/nested_diff.py`
- `/root/task/conflict_grouping.py`
- `/root/task/hr_records.json`
- `/root/task/finance_records.json`
- `/root/task/README.md`

Expected outputs:
- `/root/task/differences_report.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/differences_report.json`.
The JSON must include `total_differences` and `differences`. Each difference entry must include an employee/record identifier, a dotted `path` such as `address.street`, the HR/source-A value, the Finance/source-B value, and grouping/context information. Use recursive comparison so nested paths including address and compensation conflicts are reported while unchanged top-level fields are not.

