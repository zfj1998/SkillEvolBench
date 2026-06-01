# Task: Repair The ERP Sales Export Pipeline

The files for this task are under `/root/task`.

I need a clean sales summary from the ERP export in `/root/task/sales.csv`.
Right now the script under `/root/task/process_sales.py` is failing against the export we received from finance.

What you should do:
1. Read the CSV from `/root/task/sales.csv`.
2. Fix the schema handling in the existing code so the script can use the canonical columns `id`, `name`, `amount`, and `date`.
3. Keep the analysis logic intact: calculate the grand total and the per-name totals/averages.
4. Save the final result to `/root/task/output.json`.

Please update the existing files in `/root/task` in place. Do not move the project or replace it with a stub.


## Required Output Schema
Write `/root/task/output.json` as a JSON object with these required fields:
- `grand_total` (number): total of the cleaned `amount` column, rounded to 2 decimals.
- `row_count` (integer): number of input rows retained after schema cleanup.
- `summary` (array of objects): one object for each distinct `name`; each object must at least contain `name` (string), and may carry per-name totals/counts for auditability.
- `schema_report` (object): includes `id_dtype`, showing that the cleaned `id` column is usable as an integer schema field.

Design contract: inspect and normalize CSV headers before selecting columns, including leading/trailing whitespace on `id` and `amount`. Cast or validate the cleaned `id` column as integer-compatible. Do not bypass the schema problem by selecting columns by position.
