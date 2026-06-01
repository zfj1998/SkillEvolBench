# Task: Merge Customer Profiles With Order Summaries

The task files are in `/root/task`.

A revenue coverage export is currently dropping customers that do not yet have orders. Update the existing pipeline so the merged dataset still includes every customer, while clearly indicating which customers have no order history.

What to do:
1. Inspect the schema of `customers.csv` and `orders_summary.csv`.
2. Fix the merge pipeline under `/root/task` so all customers are preserved.
3. Keep the merged output structured and auditable in `output.json`.

Do not replace the project with a stub. Make the fix in place under `/root/task`.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): exactly one output row per customer.
- `records` (array of objects): each customer row must include `customer_id`, customer attributes, `total_orders` (integer), `total_amount` (number rounded to 2 decimals), `last_order_date` (string), and `has_orders` (boolean).
- `unmatched_customers` (object): includes `missing_count` (integer) and `missing_customer_ids` (array of integer customer IDs) for customers with no order history.

Design contract: preserve all customers with a left join, fill missing numeric order fields with `0`, fill missing `last_order_date` with an empty string, set `has_orders` explicitly, and avoid duplicate customer IDs.
