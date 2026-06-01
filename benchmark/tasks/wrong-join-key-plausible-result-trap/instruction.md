# Task: Merge Users With Transactions For Spending Totals

The task files are in `/root/task`.

An analyst needs total spending per user, but the merged output currently looks plausible while still being wrong. Inspect the schemas carefully before choosing the join key.

What to do:
1. Inspect `users.csv` and `transactions.csv`.
2. Fix the merge path so transactions attach to the correct user records.
3. Save the spending summary to `output.json`.

Make the fix in place under `/root/task`. Do not replace the project with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `merged_row_count` (integer): count of joined transaction rows after using the correct keys.
- `average_transactions_per_user` (number): average transaction count in the spending summary.
- `records` (array of objects): each object has `user_id`, `name`, `transaction_count`, and `total_spending`.

Design contract: join `users.id` to `transactions.user_id`; do not join on similarly named transaction IDs. Clean both schemas before merging, preserve the expected transaction coverage, and aggregate spending by user.

