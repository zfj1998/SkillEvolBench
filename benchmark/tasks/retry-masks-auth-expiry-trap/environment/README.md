# Environment Plan: E2-LS2-T5

Role: `adversarial`
Gap focus: `Trap: 401 auth expiry needs request repair, not blind retries.`

Scenario:
The authenticated API issues very short-lived bearer tokens. A transient `503` should be retried, but a `401 token_expired` should trigger token refresh rather than repeated use of the same stale token.

Starter files:
- `auth_client.py`
- `mock_auth_api.py`
- `docs/auth-recovery.md`

Key design notes:
The trap is a generic retry path that treats `401` and `503` as equally retryable.
