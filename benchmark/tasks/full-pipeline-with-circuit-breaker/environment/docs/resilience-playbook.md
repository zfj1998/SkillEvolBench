The downstream client is supposed to implement a small breaker:

- `closed`: normal traffic
- `open`: fail fast during cooldown
- `half_open`: allow a limited probe after cooldown

The goal is to stop hammering a failing dependency while still recovering automatically when it comes back.

Operational notes:
- cooldown is based on the configured breaker timeout, not recent healthy traffic
- half-open should allow a small probe budget, then either re-open on failure or close immediately on success
- fail-fast responses while open should not count as new downstream failures
