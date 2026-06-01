# Task: Repair The Log Timeline Sorter

The files for this task are under `/root/task`.

The operations team needs the server logs in chronological order, but the current sorter in
`/root/task/process_logs.py` is still using the export-facing date representation too directly.

What you should do:
1. Fix the existing sorting logic so `/root/task/server_logs.csv` is ordered oldest first.
2. Keep the output complete and save the sorted rows to `/root/task/output.json`.
3. Preserve all rows and keep the sort grounded in actual dates, not display strings.

Please update the code in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of log rows retained.
- `first_date` (string): display date of the first sorted record.
- `last_date` (string): display date of the last sorted record.
- `records` (array of objects): all log records in chronological order, preserving the original record fields.

Design contract: parse `M/D/YYYY` and `MM/DD/YYYY` strings as dates before sorting. Sort by parsed date, then time, then `log_id` for deterministic ties using a stable sort such as pandas `kind="mergesort"`. Do not sort directly on the raw date string.
