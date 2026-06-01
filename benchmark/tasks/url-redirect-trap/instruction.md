# Task: Fetch the Latest Dataset Through the Configured Endpoint

The worker in `/root/task` should fetch the current dataset by:
1. reading the configuration endpoint,
2. extracting the current data URL from the response,
3. requesting that endpoint,
4. saving the latest dataset to `/root/task/latest_data.json`.

The starter already has an endpoint-resolution layer, but it still leans on the migration-era legacy URL when both old and new endpoints are present.

Start here:
- `/root/task/README.md`
- `/root/task/latest_data.py`
- `/root/task/endpoint_registry.py`
- `/root/task/payload_writer.py`
- `/root/task/mock_api.py`
- `/root/task/docs/migration_notes.md`

What I need:
1. Start with the config endpoint.
2. Use the current endpoint from the config response.
3. Do not fall back to the old `/v1` dataset.
4. Save the latest dataset to `/root/task/latest_data.json`.

Save all edits under `/root/task`. Do not move the project outside `/root/task`, and do not replace it with a stub.

Output contract:
- Write `/root/task/latest_data.json` as an object with `version` and `records`.
- `version` must be `v2`; `records` is an array of objects with `date` and `value`, and the provided latest records are for 2024.
