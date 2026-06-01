# Task: Operations Quality Report

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current operations-quality pipeline.
2. Update the files under `/root/task`.
3. Save the final quality report to `/root/task/output.json`.

Operations needs a monthly report with a data-quality assessment, not just raw metrics. The current pipeline loads data, but it is supposed to catch structural, statistical, and reconciliation issues before assigning a confidence level.

Review the files in `/root/task` directly. In particular:

- `/root/task/operations.db`
- `/root/task/international_offices.csv`
- `/root/task/README.md`
- `/root/task/rowcount_guard.py`
- `/root/task/revenue_anomaly.py`
- `/root/task/consistency_guard.py`
- `/root/task/office_registry.py`
- `/root/task/confidence_policy.py`
- `/root/task/build_operations_quality_report.py`

The final JSON should include discovered issues, a confidence level, and corrected report figures where invalid or duplicate records can be isolated safely.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_counts` (object): counts for `monthly_revenue`, `department_budget`, `projects`, and `project_departments`.
- `issues` (array of objects): each issue has `kind`, `source`, `detail`, and `impact`; expected issue kinds include `duplicate_region_month_batches`, `revenue_spike`, `null_department`, `invalid_office_status`, and `allocation_mismatch` when present.
- `cross_query` (object): includes `projects_total`, `allocations_total`, and `match`, using cent-level tolerance of 0.01.
- `office_registry` (object): includes `row_count`, `invalid_status_rows`, and raw `rows`; valid statuses are only `active` and `inactive`.
- `confidence` (string): `high` for no issues, `medium` for one issue, and `low` for two or more issues.
- `corrected_total_revenue` (number): revenue after duplicate region-month batches are collapsed.

Design contract: run layered sanity checks: row counts, null handling, duplicate region/month batch detection, revenue-spike detection, office-status validation, and cross-query reconciliation. Detected issues must affect the final confidence level.

