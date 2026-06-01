# E4-LS4-T5 — Extract This Year's Revenue Without Trusting the Wrong Page Pointer

The task files are in `/root/task`.

You have a financial extraction helper that starts from an internal page reference in
`annual_report.md`. The reference is misleading: it points at a revenue table for the
prior year, while the current-year table appears later in the document.

Fix the starter so it validates the referenced section before using it and extracts the
actual current-year revenue comparison.

Relevant files:
- `/root/task/extract_latest_revenue.py`
- `/root/task/reference_resolver.py`
- `/root/task/table_validator.py`
- `/root/task/annual_report.md`
- `/root/task/README.md`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write the sibling output file `output/revenue_analysis.md` (`/root/output/revenue_analysis.md` in the default container layout).
The markdown must extract this year's revenue comparison from the current-year table, report the FY2023 revenue value `118.3`, mention that the correct table is on page 47, and not use the FY2022 page-23 value as this year's revenue. It should call out or account for the incorrect internal page reference.

