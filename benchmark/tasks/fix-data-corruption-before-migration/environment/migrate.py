"""Migration: Add updated_at column and backfill from created_at.

Simulates: ALTER TABLE events ADD COLUMN updated_at TIMESTAMPTZ;
           UPDATE events SET updated_at = created_at;

In PostgreSQL, when inserting a naive timestamp (TIMESTAMP WITHOUT TIME ZONE)
into a TIMESTAMPTZ column, PostgreSQL interprets it as UTC.
But our created_at values are actually in America/New_York local time.
"""
from datetime import datetime, timezone
from models import get_all_records
from timezone_policy import attach_local_timezone


def run_migration():
    """Execute the migration - add updated_at and backfill."""
    records = get_all_records()
    migrated = []

    for record in records:
        # Simulates PostgreSQL behavior:
        # naive datetime inserted into TIMESTAMPTZ is treated as UTC
        record["created_at_local"] = attach_local_timezone(record["created_at"])
        record["updated_at"] = record["created_at"].replace(tzinfo=timezone.utc)
        migrated.append(record)

    print(f"Migration complete: {len(migrated)} records updated")
    return migrated


if __name__ == "__main__":
    run_migration()
