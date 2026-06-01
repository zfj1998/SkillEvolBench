# Task: Convert a multi-sheet Excel workbook to CSV exports for analysis

The task files are in `/root/task`.

The workbook contains operational data, lookup/reference data, and a formula-driven summary sheet. The default one-sheet read is not enough here.

Start by reading:
- `/root/task/sales_workbook.xlsx`
- `/root/task/convert_excel.py`
- `/root/task/workbook_manifest.py`
- `/root/task/formula_capture.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write an `/root/task/output/` directory containing `Data.csv`, `Reference.csv`, `Summary.csv`, and `loss_report.json`.
Each CSV corresponds to one workbook sheet. `Data.csv` must preserve 100 source data rows; `Reference.csv` must preserve 20 reference rows. `Summary.csv` must contain formula results as values, not formula strings beginning with `=`, and the `total_revenue` values must match `expected_summary.json` by category. `loss_report.json` must be a JSON array describing formula/value conversion notes.

