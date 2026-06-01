"""Data models and simulated database records.

Note: created_at values are stored as naive datetimes (no timezone info).
These represent local times in America/New_York timezone (EST/EDT).
"""
from datetime import datetime

# Simulated database records
# created_at is a naive datetime representing EST/EDT local time
RECORDS = [
    {"id": 1, "name": "Event A", "created_at": datetime(2024, 1, 15, 10, 30, 0)},
    {"id": 2, "name": "Event B", "created_at": datetime(2024, 2, 20, 14, 0, 0)},
    {"id": 3, "name": "Event C", "created_at": datetime(2024, 3, 10, 8, 15, 0)},
    {"id": 4, "name": "Event D", "created_at": datetime(2024, 4, 5, 23, 45, 0)},
    {"id": 5, "name": "Event E", "created_at": datetime(2024, 5, 12, 6, 0, 0)},
]

# Known correct event times for verification
# These are the actual local times when events occurred
KNOWN_EVENT_TIMES = {
    1: {"hour": 10, "tz": "EST"},   # Jan - EST
    2: {"hour": 14, "tz": "EST"},   # Feb - EST
    3: {"hour": 8,  "tz": "EDT"},   # Mar 10 - EDT (after spring forward)
    4: {"hour": 23, "tz": "EDT"},   # Apr - EDT
    5: {"hour": 6,  "tz": "EDT"},   # May - EDT
}


def get_all_records():
    """Get all records from the database."""
    return [dict(r) for r in RECORDS]
