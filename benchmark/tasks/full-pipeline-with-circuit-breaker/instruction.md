# Task: Add a Real Circuit Breaker to the Downstream Client

The client in `/root/task` is still too willing to hammer a failing downstream service.

We need proper breaker behavior here: count consecutive failures, open the circuit when the threshold is reached, fail fast during the cooldown window, then probe recovery in half-open before returning to normal traffic.

Start here:
- `/root/task/README.md`
- `/root/task/breaker_client.py`
- `/root/task/breaker_state.py`
- `/root/task/probe_gate.py`
- `/root/task/mock_breaker.py`
- `/root/task/docs/resilience-playbook.md`

What I need:
1. Protect the downstream service during sustained failure.
2. Stop sending traffic while the circuit is open.
3. Probe recovery in half-open before fully closing the breaker again.
4. Save all changes under `/root/task`.

Do not move the project outside `/root/task`, and do not replace it with a stub.

Return contract:
- `ResilientClient.get_resource(clock)` must return a dictionary. Success responses include `state` and `body`; fail-fast or downstream failures include `state` and `error`.
- Valid states are `closed`, `open`, and `half_open`. A successful half-open probe must immediately return the client to `closed`.
- Fail-fast responses while the circuit is open must not call the downstream service and must not count as new downstream failures.

Cooldown rule:
- Ignore the legacy `success_budget` cooldown-shortening heuristic. The next half-open probe time must be based on the configured breaker timeout.
