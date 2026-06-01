# Task: Quarterly Revenue Sanity Review

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current quarterly revenue pipeline.
2. Update the files under `/root/task`.
3. Save the final validated quarterly report to `/root/task/output.json`.

Finance needs a quarterly revenue report from the transaction export. The raw query runs successfully, but the report is supposed to detect implausible spikes before anyone publishes it.

Review the files in `/root/task` directly. In particular:

- `/root/task/transactions.csv`
- `/root/task/README.md`
- `/root/task/quarterly_baseline.py`
- `/root/task/batch_fingerprint.py`
- `/root/task/build_quarterly_revenue_report.py`

The final JSON should include the raw quarterly totals, any detected anomaly, the suspected root cause, and corrected totals if duplicate-import batches are found.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `quarterly_revenue` (object): raw totals for `Q1` through `Q4`.
- `anomalies` (array): anomaly objects with at least `quarter`, `revenue`, `baseline`, and `ratio_to_baseline`.
- `duplicate_batches` (object): duplicate import groups found by content fingerprinting, not by repeated batch IDs alone.
- `corrected_quarterly_revenue` (object): quarter totals after excluding redundant duplicate batches.
- `sanity_summary` (object): includes `baseline_revenue`, `anomaly_count`, `duplicate_batch_groups`, and a root-cause note when duplicates are found.

Design contract: flag revenue as anomalous when it exceeds the median-style baseline by more than 3x. Identify duplicate August imports by comparing batch content fingerprints, keep one canonical batch per duplicate group, and leave non-duplicate quarters unchanged.

