# Task: Primary/backup product merge

The task files are in `/root/task`.

This client collects product data from a primary API and uses a backup API only when a primary record is invalid.

Start here:
- `/root/task/fetch_products.py`
- `/root/task/record_validator.py`
- `/root/task/fallback_client.py`
- `/root/task/merge_policy.py`
- `/root/task/integration_notes.md`

What to do:
1. Keep the current primary-first retrieval flow.
2. Validate primary records before deciding whether to keep them or replace them.
3. Use backup data only for the records that are actually invalid.
4. Produce a clean merged dataset in `/root/task/output.json`.

Output contract:
- Write `/root/task/output.json` as an array of 20 clean product records.
- Each record must include `id`, `name`, `price`, `currency`, `in_stock`, and `updated_at`. Prices must be non-negative, names must be present and non-empty, and fallback rows should replace only invalid primary records.
