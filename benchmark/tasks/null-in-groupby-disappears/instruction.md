# Task: Regional Sales Totals

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Calculate total sales per region from `/root/task/regional_sales.csv` and save the result to `/root/task/output.json`.

This regional sales extract comes from several CRM feeds that do not use one consistent region label. The commercial ops team still expects a complete regional rollup, including unresolved rows that could not be mapped cleanly.

Work directly with the files in `/root/task`:

- `/root/task/README.md`
- `/root/task/regional_sales.csv`
- `/root/task/region_normalizer.py`
- `/root/task/aggregation_audit.py`
- `/root/task/aggregate_regional_sales.py`

The output should be JSON and should include both the grouped result and enough reconciliation metadata to show that the regional totals still add up to the source total.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `records` (array of objects): grouped regional totals. Each object has `region` and `total_amount`.
- `source_total` (number): total before grouping.
- `grouped_total` (number): sum across all groups after null-safe grouping.
- `unresolved_row_count` (integer): number of rows whose region was missing and therefore assigned to the explicit unknown group.
- `reconciliation` (object): audit comparing source and grouped totals.

Design contract: missing regions must not disappear from groupby output. Normalize missing/blank regions into the explicit unknown region label used by the starter pipeline and include that group in reconciliation metadata.

