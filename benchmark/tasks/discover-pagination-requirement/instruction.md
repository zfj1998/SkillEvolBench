# Task: Get the Full Catalog Export

The request sounds simple: pull the full product catalog from the API and write it to `output.json`.

The catch is that the API only returns one page at a time, and the current client still treats an almost-complete export as good enough.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/catalog_response.py`
- `/root/task/catalog_audit.py`
- `/root/task/mock_api.py`
- `/root/task/docs/catalog-api-notes.md`

What I need:
1. Retrieve the full catalog, not just the first few pages.
2. Detect pagination from the API response instead of assuming the first page is complete.
3. Keep the final output in the original API order.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of product objects with `id` and `sku`, preserving original API order. The provided catalog has exactly 120 products.
- Write `trace.json` as an object with a `trace` array of API calls so the retrieval path shows that pagination was discovered and followed.
- Each `trace.json` trace entry must include `endpoint`, `page`, `per_page`, `returned_ids`, `has_more`, and `total`.
