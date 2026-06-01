# Task: Repair The Revenue Normalization Job

The files for this task are under `/root/task`.

The transaction export in `/root/task/transactions.csv` is being fed into `/root/task/process_transactions.py`,
but the revenue normalization is too fragile for the kinds of values the operations team actually enters.

What you should do:
1. Fix the existing revenue parsing and cleaning flow.
2. Preserve the intended output: compute total revenue and category totals, then save them to
   `/root/task/output.json`.
3. Keep invalid or empty revenue values from crashing the job, but do not silently lose values that
   can be normalized into valid numbers.

Please update the existing files in `/root/task` in place.


## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `total_revenue` (number): total revenue after converting all supported amount formats, rounded to 2 decimals.
- `valid_row_count` (integer): count of rows whose amount is numeric after cleanup.
- `category_totals` (object): keys are category names and values are cleaned revenue totals rounded to 2 decimals.
- `dropped_row_count` (integer): count of rows excluded because required amount/category data could not be parsed.
- `anomaly_report` (object): audit details with `null_like_rows` (integer count of empty/`N/A`/`null`/`-` amount rows) and `parse_failures` (integer count of non-null amount values that still could not be parsed).

Design contract: handle plain numbers, comma-formatted strings, currency-prefixed strings, accounting negatives like `(123.45)`, and `N/A`/empty/null values without silently dropping supported numeric strings.
