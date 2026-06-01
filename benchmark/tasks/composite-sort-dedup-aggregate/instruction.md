# Task: Rebuild The Transaction Ordering Pipeline

The files for this task are under `/root/task`.

The log in `/root/task/transaction_log.csv` is being fed into `/root/task/process_transaction_log.py`,
but the current pipeline is still too close to the raw export format. We need a clean, deduplicated,
aggregated output that is sorted deterministically.

What you should do:
1. Clean the log fields that are needed for sorting and aggregation.
2. Remove duplicate transactional records before aggregation.
3. Aggregate by product and date, sort the final output deterministically, and save it to
   `/root/task/output.json`.

Please update the code in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of final product/date aggregate rows after semantic deduplication.
- `records` (array of objects): each object has `product_id`, `date`, `total_amount`, and the aggregate/count fields produced by the transaction pipeline.

Design contract: remove semantic duplicate transactions, aggregate by normalized product and parsed date, then sort deterministically by parsed date and natural numeric product ID. Two raw rows are semantic duplicates when their normalized `date`, `product_id`, `customer_id`, `amount`, `quantity`, and `channel` fields all match; keep only one such transaction before aggregation.
