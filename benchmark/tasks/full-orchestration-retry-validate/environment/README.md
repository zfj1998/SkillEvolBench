End-to-end user-processing workflow.

Relevant pieces:
- `request.json` contains the target `user_id`.
- `auth_session.py` owns auth and bearer-header propagation.
- `spec_router.py` chooses the downstream spec endpoint.
- `job_poller.py` handles polling, wait intervals, and transient 503 retries.
- `result_validator.py` verifies that the final payload matches the chosen spec.
- `mock_api.py` simulates the auth, branch, async job, and final result APIs.

Expected behavior:
- auth → user lookup → correct branch → submit async job → poll with retry → fetch result → validate → save
- the same bearer token should be used throughout
- 503 during polling should be retried
- final saved result should match the premium path for `user_1`
