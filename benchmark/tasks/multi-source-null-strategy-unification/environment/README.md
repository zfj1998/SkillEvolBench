## Unified Supplier Inventory

This task merges three supplier exports into one clean inventory summary.

The supplier feeds are intentionally inconsistent:

- Supplier A mostly uses empty strings for missing values.
- Supplier B uses string tokens such as `N/A` and `null`.
- Supplier C uses numeric sentinels like `-1` and `-999`.

Business rules matter here:

- `stock = 0` is valid for every supplier and means out of stock.
- `price = 0` is valid for suppliers A and B.
- `price = 0` is **not** valid for supplier C.

The final `output.json` should include:

- total record count
- valid / missing price counts
- total stock and out-of-stock counts
- per-source null audit
- per-category summary

Do not apply one global missing-value rule to every column and every supplier. That is the core failure mode in this task.
