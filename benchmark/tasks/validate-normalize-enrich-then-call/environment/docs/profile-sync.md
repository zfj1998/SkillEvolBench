# Profile Sync Notes

The transaction service can backfill missing request fields from profile data, but profile data is not guaranteed to be complete.

Observed edge cases:
- `timezone` can be `null`
- `currency` can be `null`
- some users are missing from the profile service entirely

The outbound transaction API still expects a fully normalized payload.
