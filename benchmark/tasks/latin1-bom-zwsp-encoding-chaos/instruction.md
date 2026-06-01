# Task: Stabilize The German Revenue Export Loader

The files for this task are under `/root/task`.

Our regional revenue loader in `/root/task/process_revenue.py` keeps breaking on the export in
`/root/task/revenue.csv`. This file came from the DACH reporting team and the current loader is
too optimistic about headers and amount formatting.

What you should do:
1. Fix the existing loader so it can read `/root/task/revenue.csv` reliably.
2. Preserve the intended output: totals per region and basic schema diagnostics written to
   `/root/task/output.json`.
3. Make sure the cleaned output keeps all valid rows instead of silently dropping rows that only
   need normalization.

Please update the code in `/root/task` in place. Do not replace the workflow with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `region_totals` (object): keys are region names and values are normalized amount totals rounded to 2 decimals.
- `row_count` (integer): number of rows loaded from the CSV.
- `clean_row_count` (integer): number of rows retained after decoding and value cleanup.
- `sample_names` (array of strings): representative decoded names used as an encoding sanity check.
- `schema_report` (object): includes `raw_headers`, `canonical_headers`, and `rejected_rows`.

Design contract: load the CSV with an explicit encoding strategy that preserves names such as `Muller`/`Müller`, remove BOM and zero-width spaces, normalize `amount` to numeric values, and retain every valid row.

