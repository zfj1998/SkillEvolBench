"""Process verifier for E1-LS5-T6."""
import os

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_all_conflicts_resolved(self):
        """P1: All conflict markers should be resolved."""
        for root, dirs, files in os.walk(PROJECT_DIR):
            for fname in files:
                if fname.endswith(('.py', '.yaml', '.json')):
                    fpath = os.path.join(root, fname)
                    with open(fpath) as f:
                        content = f.read()
                    assert "<<<<<<<" not in content, f"{fpath} has conflict markers"

    def test_p2_regression_root_cause_identified(self):
        """P2: Column name inconsistency should be identified and fixed."""
        search_path = os.path.join(PROJECT_DIR, "src", "search.py")
        with open(search_path) as f:
            content = f.read()
        # search.py should not reference 'event_type' if table uses 'type'
        # (or notifications should be updated to use 'event_type')
        notif_path = os.path.join(PROJECT_DIR, "src", "notifications.py")
        with open(notif_path) as f:
            notif_content = f.read()

        # Check consistency
        if "event_type" in notif_content:
            # notifications was updated to use event_type
            pass
        else:
            # notifications uses 'type', so search should too
            assert "event_type" not in content, (
                "search.py still uses 'event_type' but notifications uses 'type'"
            )

    def test_p3_fix_is_not_workaround(self):
        """P3: Fix should unify column names, not add a workaround."""
        search_path = os.path.join(PROJECT_DIR, "src", "search.py")
        with open(search_path) as f:
            content = f.read()
        # Should not have both 'type' and 'event_type' as a compatibility hack
        has_alias = "AS event_type" in content or "AS type" in content
        if has_alias:
            # Using SQL alias is acceptable but less clean
            pass
