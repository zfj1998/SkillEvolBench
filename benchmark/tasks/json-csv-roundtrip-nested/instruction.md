# Task: Convert nested JSON to CSV and back without losing structure or types

The task files are in `/root/task`.

This migration supports temporary spreadsheet editing, so the roundtrip matters as much as the forward conversion.

Start by reading:
- `/root/task/input.json`
- `/root/task/roundtrip.py`
- `/root/task/flatten_policy.py`
- `/root/task/roundtrip_check.py`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/flattened.csv`, `/root/task/roundtrip.json`, and `/root/task/verification.json`.
`flattened.csv` is the intermediate flat representation with one data row and dot-separated column names for nested object paths. `roundtrip.json` must use the exact same recursive JSON schema as `input.json`: top-level object, same keys, same nested objects/arrays, and preserved nulls, booleans, strings, integers, and floats. `verification.json` must be an object with exactly these required keys: `lossless` (boolean, true only when `roundtrip.json` recursively equals `input.json`) and `exact_match` (boolean, true only when the restored object is byte-for-byte equivalent after JSON parsing). Additional diagnostic keys are allowed only if they do not replace these two required fields. Keep the public `flatten` and `unflatten` functions in the conversion policy so the roundtrip can be verified directly.
