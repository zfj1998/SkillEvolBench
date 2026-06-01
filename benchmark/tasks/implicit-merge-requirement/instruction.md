# E4-LS5-T4 — Clean Up the Customer List

The task files are in `/root/task`.

The request is intentionally underspecified: the directory already contains multiple source
exports, and "clean up the customer list" implicitly means discovering them, merging them,
deduplicating them, and keeping the most complete contact information.

Relevant files:
- `/root/task/clean_customer_list.py`
- `/root/task/source_discovery.py`
- `/root/task/customer_merge_policy.py`
- `/root/task/merge_audit.py`
- `/root/task/crm_export.csv`
- `/root/task/newsletter_list.csv`
- `/root/task/event_attendees.csv`
- `/root/task/README.md`

Expected outputs:
- `/root/task/customer_list.csv`
- `/root/task/customer_merge_audit.json`

Save all edits under `/root/task`.

## Required Outputs and Schema
Write `/root/task/customer_list.csv` and `/root/task/customer_merge_audit.json`.
`customer_list.csv` must contain the columns `email`, `name`, `phone`, `city`, `company`, `tag`, and `_sources`; it must contain the cleaned unique customer list with no duplicate emails, at least 700 rows for the provided data, and enough identity fields to keep at least 85% of rows complete. It must combine CRM, newsletter, and event attendee inputs and cover at least 90% of known emails from `ground_truth.json`.

`customer_merge_audit.json` must contain `raw_records` (integer), `unique_records` (integer), `sources_seen` (array of discovered input filenames), and `dedup_method` (string). The raw count must equal the number of input rows read before deduplication, and the unique count must equal the number of rows written to `customer_list.csv`.
