# Task: Electronics Catalog Extract

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current extraction logic and its sanity checks.
2. Update the files under `/root/task`.
3. Save the final validated extract to `/root/task/output.json`.

The merchandising team wants a validated extract of all active Electronics products. The catalog contains about 5,000 rows spread across roughly 5 categories, so the final Electronics slice should be on the order of one fifth of the catalog rather than a tiny handful of rows.

Review the files in `/root/task` directly. In particular:

- `/root/task/products.db`
- `/root/task/README.md`
- `/root/task/category_normalizer.py`
- `/root/task/rowcount_guard.py`
- `/root/task/query_electronics_report.py`

The final JSON should include the extracted records and enough sanity-check information to justify that the result set is plausible before downstream teams use it.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `category` (string): exactly `Electronics`.
- `row_count` (integer): number of cleaned Electronics products, expected to be roughly 1000 and within the documented audit band.
- `average_price` (number) and `total_stock` (integer).
- `rowcount_audit` (object): includes `expected_min`, `expected_max`, and `rowcount_reasonable`.
- `requery_performed` (boolean): true if the initial query was corrected after row-count validation.
- `records` (array of objects): each product has `id`, `name`, `category`, `price`, and `stock_quantity`; every record category must be `Electronics`.

Design contract: do not rely on a narrow raw SQL category predicate alone, because hidden Unicode and BOM characters appear in the category column. Read enough candidate rows, normalize each row with `normalize_category(...)`, validate row count against the approximate catalog distribution, and correct the query if the normalized result is implausibly small.
