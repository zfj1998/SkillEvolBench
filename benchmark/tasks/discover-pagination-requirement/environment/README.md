# Environment: E2-LS3-T4

Scenario:
The catalog API defaults to 25 products per page. The product manager asked for "all products", but the starter still carries a weak completeness audit that can stop one page early.

Starter files:
- `solution.py`: export entrypoint
- `catalog_response.py`: response normalization helpers
- `catalog_audit.py`: completeness heuristics
- `product_store.py`: append helpers for collected products
- `mock_api.py`: catalog backend with pagination metadata
- `docs/catalog-api-notes.md`: API notes from the catalog team

Key design notes:
- the starter does loop, so it does not look like a trivial one-call solution
- it still decides the export is "complete enough" once it gets within one page of the reported total
- the correct solution must keep paginating until the API itself says there is no more data
