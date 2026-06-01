# Task: Import the Batch and Reject Only the Bad Rows

HR handed me `/root/task/employees.json` and wants the batch importer fixed.

We should create accounts for the valid rows, reject the invalid rows with structured per-row errors, and return a useful summary at the end. Invalid entries must not block the valid ones.

Start here:
- `/root/task/README.md`
- `/root/task/batch_import.py`
- `/root/task/employees.json`
- `/root/task/docs/hr-import-notes.md`

What I need:
1. Process the full batch in order.
2. Create the valid accounts.
3. Report the invalid rows with their original index and field-level errors.
4. Save the updated implementation under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- The batch contains 10 input rows. A correct run creates 4 valid accounts and rejects 6 invalid rows.
- Return a dictionary with `success`, `failures`, and `summary`.
- Each failure entry must include the original zero-based `index` and an `errors` list. Each error must include `field` and `reason`. Use distinct reasons for missing values, empty values, bad email format, and duplicate usernames.
- The summary must report `total`, `succeeded`, and `failed` counts.
