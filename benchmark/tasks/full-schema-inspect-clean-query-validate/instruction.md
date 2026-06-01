# Task: Rebuild The Dirty Revenue Validation Pipeline

The files for this task are under `/root/task`.

We have a dirty export in `/root/task/dirty_data.csv` and a finance control file in
`/root/task/expected_totals.json`. The current pipeline in `/root/task/process_pipeline.py`
is supposed to clean the data, aggregate totals by region, and validate the results against the
expected totals, but it is not strict enough.

What you should do:
1. Keep the pipeline structure: inspect schema, clean the amount column, aggregate by region, and
   validate the result against `/root/task/expected_totals.json`.
2. Repair the cleaning logic so the totals are actually trustworthy.
3. Save the final report to `/root/task/output.json`, including per-region validation results.

Please update the existing implementation in `/root/task` in place.


## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `region_totals` (object): keys are region names and values are cleaned totals rounded to 2 decimals.
- `validation_report` (array of objects): one item per expected region. Each item must include `region` and `passed`; it should also carry actual/expected totals or delta fields for auditability.

Design contract: perform schema inspection, strip zero-width characters and header whitespace, convert mixed amount formats including comma, currency, and accounting negatives, aggregate per region, then compare against `expected_totals.json` with a strict 1.0% tolerance.
