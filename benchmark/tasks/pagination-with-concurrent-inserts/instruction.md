# Task: Make the Order Export Consistent While New Rows Arrive

The order export in `/root/task` is paging through a dataset that can change while the export is running.

The current code still assumes a stable offset window, even though this API now exposes cursor pagination and the reported total can increase mid-run.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/scan_strategy.py`
- `/root/task/consistency_guard.py`
- `/root/task/mock_api.py`
- `/root/task/docs/order-feed-consistency.md`

What I need:
1. Retrieve all orders, including rows inserted during the export.
2. Avoid missing or duplicating ids when the dataset changes.
3. Keep the retrieval logic generic instead of relying on a frozen first-page snapshot.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of order objects with integer `id` values. The provided changing dataset should finish with exactly 105 unique orders, ids 1 through 105, without gaps or duplicates.
- Write `trace.json` as an object with a `trace` array that records each pagination request and enough metadata to show how the client adapted when totals changed.
