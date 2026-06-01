# Task: March Sales Report

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Inspect the current March-report pipeline.
2. Update the files under `/root/task`.
3. Save the final report to `/root/task/output.json`.

The sales team asked for a March sales report, but the data export contains malformed rows and the report still needs a basic completeness check before anyone treats it as a complete month.

Review the files in `/root/task` directly. In particular:

- `/root/task/daily_sales.db`
- `/root/task/README.md`
- `/root/task/sales_cleaning.py`
- `/root/task/calendar_guard.py`
- `/root/task/report_annotations.py`
- `/root/task/build_march_sales_report.py`

The final JSON should include the March totals, daily breakdown, and any completeness annotation needed to explain missing or invalid days.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `month` (string): `2024-03`.
- `total_revenue` and `average_daily_revenue` (numbers).
- `days_with_data` (integer).
- `missing_days` (array of strings): exact missing dates, including `2024-03-15` and `2024-03-16` for the provided data.
- `completeness` (string): `incomplete` when any March day is missing.
- `quality_note` (string): must explicitly state how many days are missing and list the missing dates.
- `daily_breakdown` (array): each item has `date`, `revenue`, and `transactions`.

Design contract: generate March sales totals from cleaned and deduplicated rows, check the expected March calendar in `calendar_guard.py`, build a completeness note in `report_annotations.py`, and use the valid cleaned rows in `build_march_sales_report.py` when checking missing days.

