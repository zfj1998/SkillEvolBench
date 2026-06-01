# Task: Inventory export

The task files are in `/root/task`.

This client fetches ten inventory pages and saves the combined result to `/root/task/output.json`.

Start here:
- `/root/task/fetch_products.py`
- `/root/task/transport_guard.py`
- `/root/task/inventory_cache.py`
- `/root/task/README.md`

What to do:
1. Keep the current fetch-and-save workflow.
2. Add the response validation that a production data export should have, even if the instruction does not spell it out.
3. Do not treat HTML error bodies or lying empty pages as valid inventory data.
4. Keep your edits in place under `/root/task`.

Output contract:
- Write `/root/task/output.json` as an array of valid inventory objects with unique `id` values.
- The provided export should contain 35 unique valid rows. HTML error bodies, empty lying pages, duplicate replay, and non-object rows are invalid and must not be saved.
- Valid inventory rows must include `id`, `name`, `price`, `currency`, and `in_stock`.

Validation details:
- Treat JSON parse errors, HTML bodies served with 200, missing `data`, and lying empty pages as invalid responses.
- Do not replay a previous last-good payload when the current response is invalid.
