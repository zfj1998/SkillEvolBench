# Task: Make the 503 Retry Strategy Production-Safe

The retry client in `/root/task` is too naive for the unstable downstream service we are calling.

This API intermittently returns `503`. We need a real retry strategy here: retries should back off, the delay should grow between attempts, and we should add jitter so every caller does not retry on the same schedule.

Start here:
- `/root/task/README.md`
- `/root/task/retry_client.py`
- `/root/task/mock_api.py`
- `/root/task/docs/reliability-runbook.md`

What I need:
1. Retry transient `503` failures.
2. Use exponential backoff instead of a fixed retry cadence.
3. Add jitter to the backoff delay.
4. Keep the retry count bounded and save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Retry contract:
- `fetch_with_retry` returns the successful response body dictionary, including the service payload and success attempt metadata.
- Retry delays must grow exponentially rather than linearly or at a fixed interval; adjacent retry sleeps should increase substantially as attempts progress.
- Add jitter from a random source on every retry so the sleep sequence is not a fixed deterministic `[1, 2, 4, ...]` schedule.
- Keep retries bounded with a configurable retry cap.
