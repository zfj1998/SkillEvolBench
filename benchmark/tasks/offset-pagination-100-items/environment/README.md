# Environment: E2-LS3-T1

Scenario:
An export worker pages through a user API that still uses offset/limit. The downstream analytics job needs all 100 users in order, with duplicate boundary rows removed.

Starter files:
- `solution.py`: current export job entrypoint
- `offset_plan.py`: request and pagination helpers
- `user_buffer.py`: in-memory merge helpers
- `retrieval_audit.py`: soft completeness checks
- `mock_api.py`: simulated paginated backend with trace recording
- `docs/offset-retrieval-notes.md`: API behavior notes from the platform team

Key design notes:
- the starter looks like a legitimate offset paginator
- a duplicated row on one page changes the returned row count
- the starter still advances offset using the returned row count and never performs real deduplication
