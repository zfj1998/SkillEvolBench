# Task: Build the Cross-Regional Sales Summary

I need a single cross-regional sales summary from the worker in `/root/task`.

Nothing in the task handoff explicitly lists the steps, but the project already has the pieces:
- discover the regional sources,
- fetch each region's sales payload,
- normalize the different payload shapes,
- convert everything into one currency,
- aggregate by product line,
- save the summary to `/root/task/summary.json`.

The starter looks organized now, but the source-selection layer still behaves like a partial rollout and misses part of the feed.

Start here:
- `/root/task/README.md`
- `/root/task/aggregation.py`
- `/root/task/source_registry.py`
- `/root/task/sales_adapter.py`
- `/root/task/currency_policy.py`
- `/root/task/mock_api.py`
- `/root/task/regions.json`
- `/root/task/exchange_rates.json`

What I need:
1. Use all required regional sources.
2. Normalize the region-specific payload shapes.
3. Convert everything into USD.
4. Aggregate by product line and compute the grand total.
5. Save the final summary to `/root/task/summary.json`.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `/root/task/summary.json` as an object with `currency: "USD"`, a `lines` array, and `grand_total_usd`.
- Each line item must include `product_line` and `total_usd`. Aggregate all configured regional sources after normalizing currencies to USD.
