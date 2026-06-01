# API Contract Notes

Legacy note from a previous sprint:
- `/admin/rebuild-index` used to validate a `dry_run` flag.
- Metrics payloads have a `tenant_id` field and an optional `trace_token`.
- Billing callbacks require HMAC verification.

None of the above is used by the current four public route handlers.
