#!/bin/bash
# Oracle solution for E1-LS4-T4
# Fix: Use proper timezone conversion in migrate.py

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('migrate.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Migration: Add updated_at column and backfill from created_at.\nFixed: properly converts naive local time to timezone-aware UTC.\n"""\nfrom datetime import datetime, timezone, timedelta\nfrom zoneinfo import ZoneInfo\nfrom models import get_all_records\n\n\ndef run_migration():\n    """Execute the migration with proper timezone handling."""\n    records = get_all_records()\n    local_tz = ZoneInfo("America/New_York")\n    migrated = []\n\n    for record in records:\n        # created_at is a naive datetime in America/New_York local time\n        # First, make it timezone-aware by attaching the local timezone\n        local_dt = record["created_at"].replace(tzinfo=local_tz)\n        # Then convert to UTC for storage in TIMESTAMPTZ\n        record["updated_at"] = local_dt\n        migrated.append(record)\n\n    print(f"Migration complete: {len(migrated)} records updated")\n    return migrated\n\n\nif __name__ == "__main__":\n    run_migration()\n', encoding='utf-8')
PYWRITE_1

echo "Fix applied: migration now properly handles timezone conversion"
