This fixture models a small HR export normalization tool.

- `fill_employee_form.py` drives the pipeline.
- `field_contract.py` defines which labels the extractor recognizes.
- `normalization_policy.py` applies template-safe formatting.
- `extraction_audit.py` records which source label populated each field.

The starter intentionally carries a stale label contract for `start_date`.
