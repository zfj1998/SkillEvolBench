# Inventory export

The client fetches ten inventory pages from an internal gateway.

Relevant files:
- `fetch_products.py`: export entrypoint
- `transport_guard.py`: response decoding and validation
- `inventory_cache.py`: last-good payload cache used by the current client
- `mock_server.py`: gateway simulator

Operational detail:
- One response is an HTML gateway error returned with a JSON content type.
- One empty page is honest.
- One empty page lies about its batch size.
