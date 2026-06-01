# Task: Build The Q3 Sales Leaderboard

The files for this task are under `/root/task`.

I need a Q3 sales leaderboard from `/root/task/transactions.csv`, but the current report generator in
`/root/task/process_leaderboard.py` is not handling ranking output the way the analytics team expects.

What you should do:
1. Use the existing transaction export to compute total Q3 sales per salesperson.
2. Produce a leaderboard in `/root/task/output.json`.
3. Make sure the leaderboard reflects the correct top performers and handles ties at the cutoff sensibly.

Please update the implementation in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of leaderboard rows returned, including ties at the cutoff.
- `records` (array of objects): leaderboard rows with `salesperson` (string) and `total_sales` (number), plus any source audit fields retained by the starter pipeline.

Design contract: aggregate sales by representative, sort by numeric `total_sales` descending with deterministic tie handling, and include all rows tied at the final rank cutoff.

