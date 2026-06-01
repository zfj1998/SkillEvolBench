# T3 Starter Notes

This task is intentionally designed so that top-level comparison is misleading:

- `employee_id`, `name`, `dept`, and `status` are stable
- real differences live under `address.*` and `compensation.*`

The starter already has a recursive diff helper and a report builder, but the current
walker short-circuits once it sees the first nested mismatch in an object. That means
paired conflicts like `address.street` + `address.zip` get under-reported.
