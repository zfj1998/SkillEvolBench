# Product feed client

This client pulls ten sequential product batches from an internal catalog API.

Relevant files:
- `fetch_products.py`: orchestration entrypoint
- `catalog_contract.py`: response validation and extraction rules
- `fallback_cache.py`: local cache used by the current client when a batch is invalid
- `mock_server.py`: test-only API simulator

Operational note:
- The upstream service may return HTTP 200 with a maintenance shell that omits `data`.
- A previous rollout added stale-batch replay as a temporary fallback. The current behavior is no longer acceptable for exports.
