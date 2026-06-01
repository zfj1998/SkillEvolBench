The order feed is in a transition period.

Current behavior:
- the API still supports offset/limit for old jobs
- cursor pagination is available for clients that need a consistent traversal
- totals can increase while an export is running because new orders may be inserted
- clients should deduplicate by `id` and verify the final count against the latest dataset view
