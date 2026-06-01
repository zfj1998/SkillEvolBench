The old retry profile came from a single-tenant batch worker and used a simple warm-up schedule. That is too deterministic for a shared downstream service.

The current service contract expects exponential backoff with jitter so a fleet of clients does not retry on the same cadence.
