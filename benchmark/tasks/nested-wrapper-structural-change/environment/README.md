# Product sync rollout

This client runs during a product API shape migration.

Relevant files:
- `fetch_products.py`: batch retrieval entrypoint
- `schema_router.py`: extraction logic for old and new response envelopes
- `rollout_policy.py`: compatibility policy used by the client
- `response_formats.md`: current contract notes from the rollout

Important:
- Old responses use `data`.
- New responses use `result.items`.
- Transitional responses may still include a stale top-level `data` field.
