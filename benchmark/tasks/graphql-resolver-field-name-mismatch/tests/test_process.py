"""Process verifier for E1-LS4-T2: graphql-resolver-field-name-mismatch."""
import os
import re

PROJECT_DIR = os.path.join(os.path.dirname(__file__), "..", "project")


class TestProcess:
    def test_p1_fix_in_resolver_layer(self):
        """P1: Fix should be in the resolver (camelCase keys) or server config (auto-convert)."""
        resolver_path = os.path.join(PROJECT_DIR, "resolvers", "user_resolver.py")
        with open(resolver_path) as f:
            source = f.read()

        # Check that resolver now returns camelCase keys
        has_camel_case = "userName" in source or "emailAddress" in source
        # Or check for auto-conversion utility
        has_converter = "camel" in source.lower() or "snake_to_camel" in source.lower()

        assert has_camel_case or has_converter, (
            "Resolver should return camelCase keys matching the schema, "
            "or use a conversion utility"
        )

    def test_p2_all_resolver_keys_match_schema(self):
        """P2: All resolver return keys should match schema field names."""
        import sys
        sys.path.insert(0, PROJECT_DIR)
        from resolvers.user_resolver import resolve_user

        schema_fields = ["id", "userName", "emailAddress", "firstName", "lastName", "createdAt"]
        result = resolve_user(None, None, id="1")

        for field in schema_fields:
            assert field in result, (
                f"Schema field '{field}' missing from resolver output. "
                f"Resolver keys: {list(result.keys())}"
            )

    def test_p3_no_frontend_workaround(self):
        """P3: Fix should NOT be a frontend workaround (accessing snake_case fields)."""
        # Check that frontend queries still use camelCase (no snake_case workaround)
        frontend_dir = os.path.join(PROJECT_DIR, "frontend")
        if os.path.exists(frontend_dir):
            for fname in os.listdir(frontend_dir):
                fpath = os.path.join(frontend_dir, fname)
                if os.path.isfile(fpath):
                    with open(fpath) as f:
                        content = f.read()
                    # Frontend should NOT reference snake_case field names
                    assert "user_name" not in content, (
                        f"Frontend file {fname} uses 'user_name' - "
                        "this is a workaround, fix should be in resolver"
                    )
                    assert "email_address" not in content, (
                        f"Frontend file {fname} uses 'email_address' - "
                        "this is a workaround, fix should be in resolver"
                    )
