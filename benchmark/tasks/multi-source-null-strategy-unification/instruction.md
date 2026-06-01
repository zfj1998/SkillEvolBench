# Task: Unified Product Inventory

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Merge the three supplier exports in `/root/task`, standardize missing values correctly, and save the final unified inventory summary to `/root/task/output.json`.

Each supplier encodes missing values differently, and the warehouse team needs one clean summary for downstream pricing and stock analytics. Some values that look suspicious are actually valid, so do not guess blindly.

Review the files in `/root/task` directly. In particular:

- `/root/task/data_dictionary.md`
- `/root/task/supplier_a.csv`
- `/root/task/supplier_b.csv`
- `/root/task/supplier_c.csv`
- `/root/task/README.md`
- `/root/task/null_policy.py`
- `/root/task/supplier_schema.py`
- `/root/task/merge_inventory.py`
- `/root/task/quality_summary.py`
- `/root/task/merge_supplier_inventory.py`

The final JSON should include aggregate metrics and enough audit information to explain how missing values were standardized across sources.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with supplier totals plus a null-standardization audit. The audit must identify missing-value counts per source and show that all source-specific markers were normalized before aggregation.

Design contract: standardize source A nulls, source B markers (`N/A`, `null`, empty string), and source C sentinels (`-999` missing while legitimate zero values are retained) according to `data_dictionary.md`, then aggregate from the unified representation.

