Transient server failures and expired credentials are not the same recovery path.

- `503` should stay on the retry/backoff path.
- `401 token_expired` should refresh auth state before retrying the protected request.

Blind retries with the same expired token waste requests and do not recover the session.
