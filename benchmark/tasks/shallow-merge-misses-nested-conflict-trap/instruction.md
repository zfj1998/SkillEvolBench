# E4-LS5-T5 — Reconcile Two Datasets and Report Real Differences

The task files are in `/root/task`.

This is the adversarial version of the family. The two datasets match perfectly at the top
level, so a shallow merge looks safe, but several records disagree inside nested `address`,
`phone`, and `compensation` objects.

Relevant files:
- `/root/task/reconcile_nested_differences.py`
- `/root/task/top_level_gate.py`
- `/root/task/deep_compare.py`
- `/root/task/source_a.json`
- `/root/task/source_b.json`
- `/root/task/README.md`

Expected outputs:
- `/root/task/reconciliation_report.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/reconciliation_report.json`.
The JSON must be an object with `total_differences` (integer) and `differences` (array). The report must not claim zero differences. Each difference object must include `record_id` (string), `path` (dot-separated string such as `address.street`), `source_a` (the value from `source_a.json`, any JSON type or null), and `source_b` (the value from `source_b.json`, any JSON type or null). Use the recursive `deep_compare.deep_diff` path in the orchestrator, and do not rely on the shallow `top_level_gate.should_skip_nested_diff` guard to skip nested comparison. Nested address, phone, and compensation conflicts must be detected.
