# Task: Repair The Customer Revenue Join

The files for this task are under `/root/task`.

I need a region-level revenue rollup by joining `/root/task/users.csv` with `/root/task/orders.csv`,
but the existing join pipeline in `/root/task/process_orders.py` is producing an empty result.

What you should do:
1. Fix the schema handling around the join key before the merge happens.
2. Keep the intended workflow: load both tables, join on the customer key, aggregate revenue by
   region, and save the final report to `/root/task/output.json`.
3. Make sure the merge result is validated instead of silently accepting an empty join.

Please update the existing files in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `merged_row_count` (integer): number of joined order rows after key normalization.
- `region_totals` (object): keys are regions and values are total revenue rounded to 2 decimals.
- `merge_report` (object): includes key dtypes before/after normalization and `unmatched_orders` (integer).

Design contract: inspect both `user_id` schemas before merging. Normalize the int/string key mismatch, including zero-padded user IDs, verify that the merge is non-empty, and preserve all order rows that have a valid matching user.

