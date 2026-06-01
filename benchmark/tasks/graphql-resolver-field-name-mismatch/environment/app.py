"""Simulated GraphQL server.

This simulates how real GraphQL libraries (like Ariadne or Graphene) resolve fields:
when a resolver returns a dict, the GraphQL engine looks up each schema field name
as a key in that dict. If the key doesn't exist, the field resolves to null.
"""
import json
import re
from field_resolution import resolve_selected_fields
from resolvers.user_resolver import resolve_user, resolve_users
from schema_runtime import USER_FIELDS


# Parse schema to get field names for each type
SCHEMA_FIELDS = {
    "User": USER_FIELDS,
}


def execute_query(query_string, variables=None):
    """Execute a GraphQL query (simplified simulation).

    Mimics real GraphQL behavior: resolver returns a dict,
    engine looks up schema field names as dict keys.
    If key not found -> null.
    """
    variables = variables or {}

    # Determine which query is being called
    if "user(" in query_string or "user (" in query_string:
        user_id = variables.get("id", "1")
        raw_result = resolve_user(None, None, id=user_id)

        if raw_result is None:
            return {"data": {"user": None}}

        # Simulate GraphQL field resolution:
        # For each field requested, look up the SCHEMA field name in the resolver's returned dict
        requested_fields = _extract_fields(query_string)
        return {"data": {"user": resolve_selected_fields(raw_result, requested_fields)}}

    elif "users" in query_string:
        raw_results = resolve_users(None, None)
        requested_fields = _extract_fields(query_string)

        resolved_list = []
        for raw in raw_results:
            resolved_list.append(resolve_selected_fields(raw, requested_fields))

        return {"data": {"users": resolved_list}}

    return {"errors": [{"message": "Unknown query"}]}


def _extract_fields(query_string):
    """Extract requested field names from a query string (simplified parser)."""
    # Find the innermost { ... } block with field names
    matches = re.findall(r'\{([^{}]+)\}', query_string)
    if not matches:
        return SCHEMA_FIELDS.get("User", [])

    # Get the last (innermost) block, which contains the actual fields
    fields_block = matches[-1]
    fields = [f.strip() for f in fields_block.split('\n') if f.strip() and not f.strip().startswith('#')]
    # Clean up any remaining query syntax
    fields = [f.strip() for f in fields if not f.startswith('query') and not f.startswith('...')]
    return fields


def run_server():
    """Demo: run some queries."""
    # Query a single user
    query = """
    query GetUser($id: ID!) {
        user(id: $id) {
            id
            userName
            emailAddress
            firstName
            lastName
        }
    }
    """
    result = execute_query(query, {"id": "1"})
    print("Single user query result:")
    print(json.dumps(result, indent=2))

    # Query all users
    query_all = """
    query GetAllUsers {
        users {
            id
            userName
            emailAddress
        }
    }
    """
    result_all = execute_query(query_all, {})
    print("\nAll users query result:")
    print(json.dumps(result_all, indent=2))


if __name__ == "__main__":
    run_server()
