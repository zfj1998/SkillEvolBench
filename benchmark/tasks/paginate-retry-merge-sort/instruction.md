# Task: Merge Both Regional Order Feeds into One Complete Export

The job in `/root/task` pages through the US and EU order APIs, retries transient failures, merges the results, removes duplicates, and writes a final sorted export.

The starter already looks like a composed pipeline, but the merge layer still uses the wrong identity boundary for shared orders, so the final export is not actually deduplicated across regions.

Start here:
- `/root/task/README.md`
- `/root/task/solution.py`
- `/root/task/regional_sync.py`
- `/root/task/merge_index.py`
- `/root/task/ordering_policy.py`
- `/root/task/mock_api.py`
- `/root/task/docs/regional-sync-notes.md`

What I need:
1. Page through both regional APIs completely.
2. Retry transient 503 responses.
3. Merge and deduplicate shared orders correctly.
4. Sort the final export by `created_at`.
5. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `output.json` as an array of order objects with `order_id`, `created_at`, `region`, and source metadata. It must contain exactly 120 unique orders sorted ascending by `created_at`.
- Write `trace.json` as an object with a `trace` array recording region, page, and status for each regional API call, including the retried transient 503.
