# Environment Plan: E2-LS2-T2

Role: `enriched`
Gap focus: `Gap 1: 503 handling needs exponential backoff plus jitter.`

Scenario:
The downstream API is unstable and returns intermittent `503`s. A robust client should avoid a fixed retry cadence and instead spread retries over time with exponential growth and jitter.

Starter files:
- `retry_client.py`
- `mock_api.py`
- `docs/reliability-runbook.md`

Key design notes:
The environment records exact retry timing, so a fixed or purely deterministic schedule will be detected.
