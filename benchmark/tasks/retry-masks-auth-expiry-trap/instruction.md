# Task: Stop Blind Retries From Hiding Token Expiry

The authenticated client in `/root/task` is treating every failure like a generic retry case, and that is the wrong behavior here.

The API requires a bearer token. Tokens expire quickly. When the token is expired we need to refresh auth state instead of repeatedly retrying the same bad request. At the same time, transient `503` failures should still be retried.

Start here:
- `/root/task/README.md`
- `/root/task/auth_client.py`
- `/root/task/mock_auth_api.py`
- `/root/task/docs/auth-recovery.md`

What I need:
1. Distinguish auth expiry from retryable server failures.
2. Refresh the token when the API says it expired.
3. Keep retry behavior for transient `503` responses.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Deliverable note: no standalone output file is required. The required artifacts are the edited authenticated client files under `/root/task`; the verifier checks token-refresh and retry behavior through the existing client/API return values.
