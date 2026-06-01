# Task: Fix The Sales Metric Extractor

The files for this task are under `/root/task`.

The extractor in `/root/task/process_amounts.py` is supposed to sum the `amount` column from the sales
export, but the export profile uses a different column naming convention than the downstream code expects.

What you should do:
1. Fix the schema handling so the amount column is found by meaning, not by an export-specific position.
2. Keep the intended output: compute the total and save it to `/root/task/output.json`.
3. Preserve compatibility with export files whose column order changes between partners.

Please update the code in `/root/task` in place.


## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `metric_column` (string): the normalized column name used for the calculation; it must be exactly `amount`.
- `total_amount` (number): sum of the `Amount`/`amount` column after case-insensitive header normalization, rounded to 2 decimals.

Design contract: normalize column names by case rather than relying on column positions. The solution must keep working if the CSV column order changes.
