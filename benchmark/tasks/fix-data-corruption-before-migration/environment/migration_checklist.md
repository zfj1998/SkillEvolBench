# Migration Checklist

1. Backfill `updated_at`.
2. Verify the report timeline still matches the known event hours.
3. Watch for local-time vs stored-time discrepancies around EST / EDT boundaries.
