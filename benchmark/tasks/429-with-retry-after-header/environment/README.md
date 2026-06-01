# Environment Plan: E2-LS2-T1

Role: `canonical`
Gap focus: `No gap exposure; the core challenge is honoring Retry-After correctly.`

Scenario:
The batch reader calls a rate-limited API for two tenant cases. The API returns `429` with a `Retry-After` header, but the wait time is dynamic per case rather than fixed globally.

Starter files:
- `retry_client.py`
- `mock_api.py`
- `docs/rate-limit-playbook.md`

Key design notes:
The client should respect the server-provided wait time, not a hard-coded local budget. One visible case uses `Retry-After = 2`, while another uses `Retry-After = 5`.
