# Task: Retry Only the Failing Step in the Sync Pipeline

The five-step sync flow in `/root/task` is wasting work when a transient failure happens in the middle of the pipeline.

The pipeline is effectively `auth -> list -> detail -> enrich -> save`. The failure happens in the detail step. We should retry that failing step, but we should not restart the completed upstream work unless it is actually invalidated.

Start here:
- `/root/task/README.md`
- `/root/task/pipeline_client.py`
- `/root/task/mock_pipeline.py`
- `/root/task/docs/pipeline-runbook.md`

What I need:
1. Keep the full sync pipeline working.
2. Retry the transient failure in the detail stage.
3. Do not rerun already-completed upstream steps unnecessarily.
4. Save all updates under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Implementation boundary:
- Keep the fix in `/root/task/pipeline_client.py`.
- Add or repair a step-local helper such as `fetch_details_with_retry(record_ids, ...)` so only the detail-fetch stage is retried.
- `api.authenticate()` and `api.list_records(token)` should run once before the retry helper; retries should call only the transient detail endpoint before continuing to enrich and save.

API and return schema:
- `api.authenticate()` returns a bearer token string.
- `api.list_records(token)` returns a list of record ids.
- `api.fetch_details(record_ids)` returns a list of detail dictionaries for those ids and may raise `TransientServiceError`.
- `api.enrich(details)` returns enriched detail dictionaries, and `api.save(enriched)` returns the final saved result dictionary.
