# E4-LS3-T4 — Complete a Partially Filled Report

The task files are in `/root/task`.

You have a report completion helper that reads a partially filled text template and a
small key-value data source. The task is implicit: the tool needs to recognize which
placeholder shapes still mean "fill me" and replace only those, without touching fields
that were already complete.

Fix the starter in place.

Relevant files:
- `/root/task/complete_report.py`
- `/root/task/placeholder_catalog.py`
- `/root/task/report_template.txt`
- `/root/task/data_source.txt`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/output/completed_report.txt` and `/root/output/placeholder_audit.txt`.
`completed_report.txt` must fill every placeholder from `report_template.txt` using `data_source.txt`, leaving no `[TBD]`, `[INSERT HERE]`, `___`, or `<PENDING>` markers. It must include fields such as project/name, owner, region, launch date, status, support tier, and budget status. `placeholder_audit.txt` must be a plain-text audit with one replaced field key per line, using the exact keys from `data_source.txt`; already-complete fields such as `Project`, `Owner`, `Support Tier`, and `Budget Status` must not appear in the audit.
