# Task: Product Feed Collection

The task files are in `/root/task`.

You are maintaining a small client that pulls ten product feed batches from an internal API and writes the combined result to `/root/task/output.json`.

Start here:
- `/root/task/fetch_products.py`
- `/root/task/catalog_contract.py`
- `/root/task/fallback_cache.py`
- `/root/task/README.md`

What to do:
1. Keep the existing workflow shape: call the API, validate each response, and save a clean combined dataset.
2. Treat HTTP 200 as transport success only. A response without usable product data is still invalid.
3. When a batch response is invalid, handle it safely instead of reusing stale payloads.
4. Save your final code changes in place under `/root/task`.

Notes:
- The API returns ten sequential batches.
- Some responses are maintenance shells with `status: "ok"` but no usable `data`.
- Do not replace the project with a stub. Fix the existing client.

Output contract:
- Write `/root/task/output.json` as an array of product objects from valid batches only. Product rows must include the current catalog fields defined by `/root/task/catalog_contract.py`.
- The provided feed should produce 40 unique valid records. Missing `data` responses must be logged as anomalies and must not cause stale data replay.
- Product rows must include `id`, `name`, `price`, `currency`, `in_stock`, and `batch`.
