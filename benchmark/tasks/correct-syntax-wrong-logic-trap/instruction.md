# Task: Active Customer Count

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current active-customer counting logic.
2. Update the files under `/root/task`.
3. Save the final validated customer summary to `/root/task/output.json`.

The business question is “how many logical customers actually placed valid orders?” The database contains duplicate customer identities, orphaned orders, and orders that should not count as customer activity.

Review the files in `/root/task` directly. In particular:

- `/root/task/store.db`
- `/root/task/README.md`
- `/root/task/customer_identity.py`
- `/root/task/order_validity.py`
- `/root/task/activity_guard.py`
- `/root/task/count_active_customers.py`

The final JSON should report the logical customer total, active and inactive counts, and enough sanity metadata to justify the number.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `logical_customer_total` (integer): deduplicated logical customer count.
- `active_customer_count` (integer): customers with at least one valid order; this should not include customers whose joined order fields are null.
- `inactive_customer_count` (integer).
- `active_customer_ids` (array of integers): sorted canonical IDs.
- `sanity` (object): includes `active_le_total` and `active_plus_inactive_equals_total` booleans.

Design contract: a query that runs is not enough. Use INNER JOIN semantics or a LEFT JOIN with an explicit non-null valid-order filter, normalize customer identity, exclude invalid/null orders, and verify that active customers cannot exceed logical customers.

