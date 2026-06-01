# Task: Product sync during API rollout

The task files are in `/root/task`.

This client pulls ten product batches during a response-format rollout. Some requests return the old shape, and some return the new nested shape.

Start here:
- `/root/task/fetch_products.py`
- `/root/task/schema_router.py`
- `/root/task/rollout_policy.py`
- `/root/task/response_formats.md`

What to do:
1. Make the client collect every batch successfully across both response formats.
2. Normalize the extracted products into one consistent output in `/root/task/output.json`.
3. Avoid stale compatibility fields when a newer nested payload is present.
4. Keep edits in place under `/root/task`.

`output.json` must be an array of 50 normalized product objects. Each object must contain `id` (integer below 9000), `name` (string), `price` (number), `currency` (string), and `in_stock` (boolean). Do not include stale discontinued products or leave the nested API wrapper shape as the final product payload.
