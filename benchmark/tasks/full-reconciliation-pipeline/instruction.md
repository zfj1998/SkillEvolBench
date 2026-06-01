# E4-LS5-T6 — Reconcile Three Systems Into One Master Dataset

The task files are in `/root/task`.

This is the full composition task in the family:

1. normalize three source schemas
2. fuzzy-match overlapping entities
3. detect nested conflicts
4. apply a source-priority resolution strategy
5. write a master dataset and a conflict log

Relevant files:
- `/root/task/run_full_reconciliation.py`
- `/root/task/entity_matcher.py`
- `/root/task/nested_conflict_reporter.py`
- `/root/task/resolution_policy.py`
- `/root/task/source_priority.py`
- `/root/task/system_a.json`
- `/root/task/system_b.json`
- `/root/task/system_c.json`
- `/root/task/README.md`

Expected outputs:
- `/root/task/master_dataset.json`
- `/root/task/conflict_log.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/master_dataset.json` and `/root/task/conflict_log.json`.
`master_dataset.json` must be an array of reconciled master record objects. Each record must include `_sources` (array of source names), `_record_ids` (array of source record IDs), `record_id`, `name`, `email`, `phone`, `department`, `address` (object with available `street`, `city`, and `zip` fields), and `compensation` (object with available `bonus` and `equity` fields). For resolved scalar fields, include the corresponding `_<field>_winner` string such as `_name_winner` or `_phone_winner`.

`conflict_log.json` must be an object with `matching_method` (string mentioning exact, phone, and nickname evidence), `resolution_strategy` (string containing the priority order `system_a > system_b > system_c`), `total_conflicts` (integer), and `conflicts` (array). Each conflict entry must include `record_id` (string), `field_path` (dotted string such as `address.street`), `source_a_value` (any JSON type or null), and `source_b_value` (any JSON type or null). The provided example files in `/root/task/master_dataset.json` and `/root/task/conflict_log.json` are normative examples of the required schema, but the implementation must regenerate them from the three source systems.
