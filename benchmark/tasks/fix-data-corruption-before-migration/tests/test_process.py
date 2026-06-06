"""Process verifier for E1-LS4-T4: fix-data-corruption-before-migration."""
import os
import re

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_migration_handles_timezone(self):
        """P1: Migration script should explicitly handle timezone conversion."""
        migrate_path = os.path.join(PROJECT_DIR, "migrate.py")
        with open(migrate_path) as f:
            source = f.read()

        # Check for timezone-aware conversion patterns
        has_tz_conversion = any([
            "AT TIME ZONE" in source,
            "pytz" in source,
            "zoneinfo" in source,
            "ZoneInfo" in source,
            "timezone(" in source and "utc" not in source.split("timezone(")[1][:20].lower(),
            "astimezone" in source,
            "localize" in source,
            "America/New_York" in source,
        ])

        # The old bug was: .replace(tzinfo=timezone.utc) treating local as UTC
        still_has_bug = "replace(tzinfo=timezone.utc)" in source

        assert has_tz_conversion or not still_has_bug, (
            "Migration should handle timezone conversion properly - "
            "not just treating local time as UTC"
        )

    def test_p2_verification_query_run(self):
        """P2: Post-migration timestamp verification should be done."""
        # Check if verify_times.py was used or report was checked
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from verify_times import verify_all_events
        from report import generate_timeline_report

        report = generate_timeline_report()
        results = verify_all_events(report["events"])
        all_correct = all(r["correct"] for r in results)
        assert all_correct, (
            f"Post-migration verification failed: "
            f"{[r for r in results if not r['correct']]}"
        )
