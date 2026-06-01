# Task: Extract quarterly financial data from PDF, persist JSON, then generate a formatted DOCX report

The task files are in `/root/task`.

This is a chained migration pipeline. The JSON step is not optional; it is the structured handoff between extraction and report generation.

Start by reading:
- `/root/task/pipeline.py`
- `/root/task/pdf_extract.py`
- `/root/task/json_bridge.py`
- `/root/task/docx_writer.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/extracted.json` and `/root/task/report.docx`.
`extracted.json` must use a quarter-keyed financial schema. Each quarter object must include revenue, expenses, and profit. Profit must be calculated from extracted revenue and expenses rather than copied from a constant. `report.docx` must open as a DOCX, include a heading such as Quarterly Financial Report, mention each quarter and value, and contain at least one structured table.
