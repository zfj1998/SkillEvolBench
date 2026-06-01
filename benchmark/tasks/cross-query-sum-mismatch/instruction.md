# Task: Revenue Cross-Check by Product Line

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current revenue-report logic.
2. Update the files under `/root/task`.
3. Save the final reconciled report to `/root/task/output.json`.

Finance wants total revenue overall and by product line from the same source database. Those two views should reconcile after the data is cleaned and joined correctly.

Review the files in `/root/task` directly. In particular:

- `/root/task/revenue.db`
- `/root/task/README.md`
- `/root/task/product_line_map.py`
- `/root/task/revenue_views.py`
- `/root/task/consistency_guard.py`
- `/root/task/reconcile_revenue_views.py`

The final JSON should show both totals, the product-line breakdown, and an audit trail explaining whether the two query paths reconcile.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `overall_total` (number): total revenue from orders.
- `product_line_total` (number): sum of corrected product-line revenue.
- `match` (boolean): true when totals reconcile within 0.01.
- `difference` (number): absolute reconciliation difference.
- `by_product_line` (object): revenue per product line.
- `mismatch_reason` (string or null): null when reconciled, otherwise a clear audit reason.

Design contract: compute product-line revenue from item-level amounts such as `item_amount`, not by duplicating full order amounts across a many-to-many join. Compare the product-line total with the overall total and investigate any mismatch above 0.01.

Keep the two auditable report-view helpers in `/root/task/revenue_views.py` named `overall_revenue_rows` and `normalized_product_line_totals`, so the reconciliation script and review checks can verify that the overall and product-line query paths remain separate.
