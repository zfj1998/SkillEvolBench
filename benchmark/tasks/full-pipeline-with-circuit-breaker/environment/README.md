# Environment Plan: E2-LS2-T6

Role: `composition`
Gap focus: `Retry logic composed with circuit-breaker state management.`

Scenario:
The downstream service enters a sustained failure window. The client should open the circuit after repeated failures, stop sending calls during cooldown, then probe recovery in half-open before resuming normal traffic.

Starter files:
- `breaker_client.py`
- `breaker_state.py`
- `probe_gate.py`
- `cooldown_policy.py`
- `mock_breaker.py`
- `docs/resilience-playbook.md`

Key design notes:
The starter implementation should look like a production breaker client with a dedicated state container, probe gate, and cooldown helper.
It should still be wrong in realistic ways:
- an old rollout policy shortens cooldown based on recent healthy traffic,
- half-open recovery does not fully close the breaker on the first successful probe,
- state transitions look plausible in code review unless the timing is exercised end to end.
