# Task: Extract invoice data, normalize it for ERP, fill the template, and validate consistency

The task files are in `/root/task`.

This is an end-to-end finance automation task:
1. extract invoice fields from the PDF
2. normalize dates and amounts for ERP
3. fill the CSV template
4. verify that the filled CSV is consistent with the source document total

The starter pipeline is close, but its normalization and template writing layers still violate the ERP contract.

Start by reading:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/date_normalizer.py`
- `/root/task/erp_writer.py`
- `/root/task/consistency_check.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Run `run_analysis.sh` so it writes `/root/task/filled_erp.csv` and `/root/task/pipeline_report.json`.
`filled_erp.csv` must use the template column order exactly: `invoice_id,invoice_date,customer,item_description,amount`; it must contain one row per invoice line item, dates normalized to `YYYY-MM-DD`, and amount values that sum to the PDF total within 0.01. `pipeline_report.json` must include `pdf_total`, `normalized` set to true, and `invoice_date` normalized to `YYYY-MM-DD`.

