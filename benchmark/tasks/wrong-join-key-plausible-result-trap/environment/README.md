# User Spending Merge

`users.csv` is a CRM export with noisy headers and several broken rows.

`transactions.csv` is a ledger export that contains both a transaction primary key (`id`) and the foreign key back to users (`user_id`).

The current join selector grabs the first overlapping identifier-looking column and produces a result that looks reasonable by row count, but attaches only one transaction per user.
