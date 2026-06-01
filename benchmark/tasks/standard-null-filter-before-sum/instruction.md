# Task: Average Order Amount

The task files are in `/root/task`.

Please make the required fix or update in place and keep the intended behavior working.

What to do:
1. Find the real issue or missing step.
2. Update the existing files under `/root/task`.
3. Keep the expected behavior correct after your changes.

Save all edits under `/root/task`. Do not move the project outside `/root/task` or replace it with a stub.
Calculate the average order amount from `/root/task/orders.csv` and save the result to `/root/task/output.json`.

This export has about 5,000 orders and occasionally includes incomplete rows from the checkout pipeline. The finance team wants the average order amount, but they also want to know whether the result looks trustworthy.

Use the files in `/root/task` directly. In particular, review:

- `/root/task/README.md`
- `/root/task/orders.csv`
- `/root/task/amount_contract.py`
- `/root/task/compute_order_metrics.py`
- `/root/task/sanity_audit.py`

The output should be a JSON object that includes the average and basic sanity metadata about the calculation.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with the total/average fields used by the starter processor plus null-audit counts. Numeric totals must exclude missing amount values and retain valid zero values.

Design contract: filter null amounts before summing and report how many rows were excluded; do not coerce missing values to zero just to make aggregation run.

