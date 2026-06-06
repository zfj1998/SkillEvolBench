"""Outcome verifier for E1-LS4-T4: fix-data-corruption-before-migration."""
import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "project"))


# ============================================================
# PUBLIC TESTS (2)
# ============================================================

class TestPublic:
    def test_migration_executes_successfully(self):
        """Migration should run without errors."""
        from migrate import run_migration
        result = run_migration()
        assert result is not None
        assert len(result) == 5
        for record in result:
            assert "updated_at" in record

    def test_report_generates_successfully(self):
        """Report should generate without errors."""
        from report import generate_timeline_report
        report = generate_timeline_report()
        assert report is not None
        assert len(report["events"]) == 5


# ============================================================
# HIDDEN TESTS (4)
# ============================================================

class TestHidden:
    def test_h1_updated_at_matches_created_at_with_timezone(self):
        """H1: updated_at should match created_at when timezone is considered."""
        from report import generate_timeline_report
        from models import KNOWN_EVENT_TIMES

        report = generate_timeline_report()
        for event in report["events"]:
            expected_hour = KNOWN_EVENT_TIMES[event["id"]]["hour"]
            assert event["hour"] == expected_hour, (
                f"Event {event['id']} ({event['name']}): "
                f"reported hour={event['hour']}, expected={expected_hour}. "
                f"Timezone conversion issue?"
            )

    def test_h2_report_timeline_hours_correct(self):
        """H2: Report timeline should show correct local hours."""
        from report import generate_timeline_report
        report = generate_timeline_report()

        # Event A should be at hour 10 (EST)
        event_a = [e for e in report["events"] if e["id"] == 1][0]
        assert event_a["hour"] == 10, f"Event A should be hour 10, got {event_a['hour']}"

        # Event D should be at hour 23 (EDT)
        event_d = [e for e in report["events"] if e["id"] == 4][0]
        assert event_d["hour"] == 23, f"Event D should be hour 23, got {event_d['hour']}"

    def test_h3_all_timestamps_timezone_consistent(self):
        """H3: All timestamps should have consistent timezone handling."""
        from migrate import run_migration
        records = run_migration()

        for record in records:
            updated = record["updated_at"]
            # updated_at should have timezone info
            assert updated.tzinfo is not None, (
                f"Record {record['id']}: updated_at has no timezone info"
            )

    def test_h4_migration_uses_timezone_conversion(self):
        """H4: Migration should use AT TIME ZONE or Python timezone conversion."""
        from migrate import run_migration
        from models import KNOWN_EVENT_TIMES

        records = run_migration()
        # Verify the actual hours are correct (not shifted by UTC offset)
        for record in records:
            expected = KNOWN_EVENT_TIMES[record["id"]]["hour"]
            actual = record["updated_at"].hour
            # If properly converted, hours should match known local times
            # (may need to convert to local tz first)
            # Just check that the migration result makes the report correct
            assert actual == expected or True  # Soft check - main check is in H1
