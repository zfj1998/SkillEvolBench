"""Database configuration."""
import os

DATABASE_TZ = os.environ.get("TZ", "America/New_York")
REPORT_TZ = os.environ.get("REPORT_TZ", DATABASE_TZ)
DATABASE_URL = "postgresql://localhost:5432/myapp"
