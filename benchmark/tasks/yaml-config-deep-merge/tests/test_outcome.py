"""Outcome verifier for E1-LS5-T3: yaml-config-deep-merge."""
import sys
import os
import yaml
import json
import pytest

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestHidden:
    def test_h1_yaml_valid(self):
        """H1: yaml.safe_load should not error."""
        config_path = os.path.join(PROJECT_DIR, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)
        assert config is not None
        assert isinstance(config, dict)

    def test_h2_both_changes_preserved(self):
        """H2: pool_size=10 AND ssl.enabled=True under database."""
        config_path = os.path.join(PROJECT_DIR, "config.yaml")
        with open(config_path) as f:
            config = yaml.safe_load(f)

        db = config.get("database", {})
        assert db.get("pool_size") == 10, f"pool_size should be 10, got {db.get('pool_size')}"

        ssl = db.get("ssl", {})
        assert ssl.get("enabled") is True, f"ssl.enabled should be True, got {ssl.get('enabled')}"
        assert ssl.get("cert_path") is not None, "ssl.cert_path missing"

    def test_h3_schema_validation(self):
        """H3: Config should match JSON Schema structure."""
        config_path = os.path.join(PROJECT_DIR, "config.yaml")
        schema_path = os.path.join(PROJECT_DIR, "config_schema.json")

        with open(config_path) as f:
            config = yaml.safe_load(f)
        with open(schema_path) as f:
            schema = json.load(f)

        # Basic structural validation
        for required_key in schema.get("required", []):
            assert required_key in config, f"Missing required key: {required_key}"

        db = config["database"]
        db_schema = schema["properties"]["database"]
        for required_key in db_schema.get("required", []):
            assert required_key in db, f"Missing database.{required_key}"

        # ssl should be nested under database
        if "ssl" in db:
            assert isinstance(db["ssl"], dict), "ssl should be a dict"
            if db["ssl"].get("enabled"):
                assert "cert_path" in db["ssl"], "ssl.cert_path missing"
