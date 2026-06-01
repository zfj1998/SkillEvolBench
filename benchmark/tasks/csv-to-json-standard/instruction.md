# Task: Convert a legacy CSV export into typed JSON records

The task files are in `/root/task`.

This migration feeds a downstream API, so type handling matters:
- IDs with leading zeros must stay as strings
- amounts with thousands separators must become numbers
- dates should stay strings

Start by reading:
- `/root/task/transactions.csv`
- `/root/task/convert_csv.py`
- `/root/task/field_rules.py`
- `/root/task/type_inference.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/output.json` as a JSON array with exactly 100 objects, one per CSV row. Each object must have exactly `id`, `name`, `date`, `amount`, and `category`.
Preserve leading-zero IDs such as `007` as strings, convert amounts with thousands separators to floats, keep dates as strings in `YYYY-MM-DD` form, and convert every input row without dropping or adding rows. Implement explicit ID and amount handling rather than relying on unsafe automatic inference.

