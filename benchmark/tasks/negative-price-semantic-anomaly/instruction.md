# Task: Pricing feed validation

The task files are in `/root/task`.

This client exports pricing data from an internal feed. The JSON shape is stable, but some records violate pricing rules and should not be published as normal products.

Start here:
- `/root/task/fetch_products.py`
- `/root/task/pricing_rules.py`
- `/root/task/README.md`

What to do:
1. Keep the existing fetch-and-save flow.
2. Validate both structure and business meaning before writing the final dataset.
3. Preserve valid zero-price records such as free samples.
4. Save your changes in place under `/root/task`.

Output contract:
- Write `/root/task/output.json` as an array of valid product pricing objects with `id` and non-negative `price`.
- The provided feed should produce 18 valid records. Negative-price records must be excluded and logged as `negative price`; zero-price free samples are valid and must be retained.
- Product pricing rows must include `id`, `name`, `price`, `currency`, and `in_stock`; optional fields such as `discount_applied` should be preserved when present.
