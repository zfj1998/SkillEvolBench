Cross-regional sales summary job.

Relevant pieces:
- `regions.json` is the source registry for all regional feeds.
- `source_registry.py` turns the registry file into the list of sources to fetch.
- `sales_adapter.py` normalizes the US / EU / APAC payload shapes into one row format.
- `currency_policy.py` converts row amounts into USD using `exchange_rates.json`.
- `mock_api.py` simulates the three regional sources.

Expected behavior:
- load all required regions from `regions.json`
- call every region API
- normalize and convert each row into USD
- aggregate by `product_line`
- save the summary to `summary.json`
