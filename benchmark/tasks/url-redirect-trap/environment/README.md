Configuration-driven data fetch flow.

Relevant pieces:
- `mock_api.get_config()` returns both the current endpoint and migration-era metadata.
- `endpoint_registry.py` chooses which endpoint to use.
- `payload_writer.py` persists the final dataset.
- `docs/migration_notes.md` captures the old dual-read behavior that the client is still carrying around.

Expected behavior:
- call `/config` first
- use the current `data_endpoint` from the response
- avoid the stale `/v1/data` dataset
- save the result to `latest_data.json`
