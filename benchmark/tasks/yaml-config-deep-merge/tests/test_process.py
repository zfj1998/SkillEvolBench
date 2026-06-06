"""Process verifier for E1-LS5-T3."""
import os
import yaml

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_ssl_nested_under_database(self):
        """P1: ssl should be nested under database (not top-level)."""
        config_path = os.path.join(PROJECT_DIR, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        # ssl should NOT be a top-level key
        assert "ssl" not in config, "ssl should be under database, not top-level"

        # ssl SHOULD be under database
        db = config.get("database", {})
        assert "ssl" in db, "ssl should be nested under database"

    def test_p2_structurally_valid(self):
        """P2: Result should be structurally valid YAML."""
        config_path = os.path.join(PROJECT_DIR, "config.yaml")

        # Check no conflict markers remain
        with open(config_path) as f:
            content = f.read()
        assert "<<<<<<<" not in content, "Conflict markers still present"
        assert "=======" not in content, "Conflict markers still present"
        assert ">>>>>>>" not in content, "Conflict markers still present"

        # Parse and verify structure
        config = yaml.safe_load(content)
        assert isinstance(config, dict)
        assert "database" in config
