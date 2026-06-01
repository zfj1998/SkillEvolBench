# Task: Respect Retry-After When the API Rate Limits Us

The client in `/root/task` is still treating rate limits like a fixed-delay problem, and that is causing repeat 429s.

We need to fetch two cases from the same API. The server returns `429` with a `Retry-After` header, and the wait time is not the same for every case. Please make the client read the real header value, wait the required amount, and keep retries bounded.

Start here:
- `/root/task/README.md`
- `/root/task/retry_client.py`
- `/root/task/mock_api.py`
- `/root/task/docs/rate-limit-playbook.md`

What I need:
1. Handle `429` responses by reading `Retry-After`.
2. Wait before retrying instead of immediately retrying.
3. Keep a retry limit so the client cannot loop forever.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Deliverable note: this is a code-modification task, not a file-generation task. Do not create a separate report file; the verifier checks the edited `/root/task/retry_client.py` behavior together with the existing mock API. Preserve the existing function/API return shapes while fixing retry behavior.
