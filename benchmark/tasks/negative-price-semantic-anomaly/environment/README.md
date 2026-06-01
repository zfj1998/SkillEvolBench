# Pricing export client

The client fetches four pricing batches and writes a filtered export.

Relevant files:
- `fetch_products.py`: orchestration entrypoint
- `pricing_rules.py`: record normalization and eligibility decisions
- `mock_server.py`: pricing feed simulator

Operational detail:
- The upstream feed sometimes emits negative prices even though the response schema is valid.
- Legitimate free samples may have `price = 0.00`.
