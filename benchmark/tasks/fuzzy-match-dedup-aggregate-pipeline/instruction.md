# Task: Build A Clean Customer Revenue Dataset From Three Sources

The task files are in `/root/task`.

You need to merge CRM, ERP, and external ratings data into one clean dataset and calculate totals per customer segment. The three sources do not agree on company names, and a weak fallback is currently causing duplicate matches.

What to do:
1. Inspect `crm_contacts.csv`, `erp_orders.csv`, and `external_ratings.csv`.
2. Resolve name mismatches, avoid duplicate/fanout merges, and build a clean unified dataset.
3. Save the final result to `output.json`.

Make the fix in place under `/root/task`. Do not replace the project with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of merged transaction/customer rows after deduplication.
- `coverage_ratio` (number): matched coverage as a fraction of expected mergeable rows.
- `records` (array of objects): cleaned merged customer rows after CRM/rating/order alignment. Each record must include:
  - `company_name` (string): retained CRM company name.
  - `city` (string): retained CRM city.
  - `contact_email` (string): retained CRM contact email.
  - `annual_revenue` (number): CRM annual revenue.
  - `canonical_company` (string): normalized merge key used across sources.
  - `segment` (string): derived revenue segment, one of `enterprise`, `mid_market`, or `growth`.
  - `company` (string or null): matched external-ratings company label.
  - `satisfaction_score` (number or null): matched external rating.
  - `review_count` (integer or null): matched external review count.
  - `order_amount` (number): deduplicated total ERP order amount for that canonical company, using `0.0` when there are no matched orders.
- `category_totals` (array of objects): aggregate totals by segment. Each object must include:
  - `segment` (string): one of `enterprise`, `mid_market`, or `growth`.
  - `total_order_amount` (number): sum of `order_amount` for records in that segment.

Design contract: fuzzy-match customer names only after normalization, resolve near-duplicate customer rows without fanout, keep coverage at or above 90%, and compute category totals from the deduplicated merged records.

Keep the existing pipeline structure and make the fix in the relevant modules:
- `company_normalizer.py` should normalize company strings and maintain an
  explicit alias map named `COMPANY_ALIASES` for known near-duplicates.
- `dedup_policy.py` should remove duplicate CRM/rating rows before merging, for
  example with a deterministic pandas `drop_duplicates` policy after sorting by
  the preferred record.
- `process_customer_totals.py` should merge on the canonical company key only,
  avoid city-only fallback fanout joins, validate one-to-one dimension joins
  where applicable, and aggregate ERP orders by canonical company before joining.

The intended solution is a real clean-match-deduplicate-aggregate pipeline, not
a hardcoded `output.json`.

For this fixture, the required `COMPANY_ALIASES` entries are the observed
cross-source aliases needed to align the same customer across CRM, ERP, and
external ratings after punctuation/case/spacing normalization:
- `acme` and `acme corporation` should canonicalize to `acme corp`.
- `globaltech` should canonicalize to `global tech`.
- `premier sol` should canonicalize to `premier solutions`.

Use these aliases as part of the general normalization policy, then deduplicate
and aggregate from the cleaned canonical keys. Do not encode final row totals or
category totals directly.
