# Timezone Migration Notes

The upstream search service moved from local-office timestamps to full ISO 8601 values with offsets.

Important contract detail:
- Range validity is determined after normalization to UTC.
- Requests may still arrive without timezone metadata during migration.
- The client is expected to apply one explicit default policy for naive timestamps.
- During fall-back DST overlaps, reject ranges that mix offsets for the repeated local hour when the end wall-clock time is earlier than the start wall-clock time on the same local date. The service treats those ranges as ambiguous local-time input instead of accepting them solely by UTC instant order.
