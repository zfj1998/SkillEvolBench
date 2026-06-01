# Revenue Coverage Export

`customers.csv` is the CRM customer master.

`orders_summary.csv` is a pre-aggregated finance extract with one row per customer that has placed at least one order.

The current export path was originally written for revenue-only dashboards, so it keeps only customers with order history. The analyst now needs a customer-complete export with a clear signal for accounts that have not ordered yet.
