# Average Order Amount Audit

`orders.csv` is a checkout export used by finance to produce a quick average-order-amount KPI.

The export is mostly clean, but some rows are partially ingested and have no usable `amount`. The current pipeline tries to be “helpful” by keeping row-count based sanity metadata, but its denominator strategy is stale and can bias the average downward.

The expected workflow is:

1. load and parse the order export
2. compute an average over valid monetary rows
3. report how many rows were excluded
4. emit a small sanity block alongside the metric

The warehouse team also wants the denominator choice to be explicit. The metric is reviewed later in a dashboard, and “average over exported rows” versus “average over valid amount rows” must not be ambiguous.
