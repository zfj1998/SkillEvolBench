#!/bin/bash
# Oracle solution for E1-LS4-T2: graphql-resolver-field-name-mismatch
# Root cause: resolver returns snake_case keys, but GraphQL schema expects camelCase
# Fix: change resolver to return camelCase keys

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
TASK_ROOT="${TASK_ROOT:-/root/task}"
cd "$PROJECT_ROOT"

python3 - <<'PYWRITE_1'
from pathlib import Path
target = Path('resolvers/user_resolver.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""User resolvers for GraphQL queries."""\nfrom models.user import get_user_by_id, get_all_users\n\n\ndef resolve_user(_, info, id):\n    """Resolve a single user query."""\n    user = get_user_by_id(id)\n    if not user:\n        return None\n    return {\n        "id": user["id"],\n        "userName": user["user_name"],\n        "emailAddress": user["email_address"],\n        "firstName": user["first_name"],\n        "lastName": user["last_name"],\n        "createdAt": user["created_at"],\n    }\n\n\ndef resolve_users(_, info):\n    """Resolve all users query."""\n    users = get_all_users()\n    return [\n        {\n            "id": u["id"],\n            "userName": u["user_name"],\n            "emailAddress": u["email_address"],\n            "firstName": u["first_name"],\n            "lastName": u["last_name"],\n            "createdAt": u["created_at"],\n        }\n        for u in users\n    ]\n', encoding='utf-8')
PYWRITE_1

python3 - <<'PYWRITE_2'
from pathlib import Path
target = Path('app.py')
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text('"""Simulated GraphQL server."""\nimport json\nimport re\nfrom resolvers.user_resolver import resolve_user, resolve_users\n\n\nSCHEMA_FIELDS = {\n    "User": ["id", "userName", "emailAddress", "firstName", "lastName", "createdAt"],\n}\n\n\ndef execute_query(query_string, variables=None):\n    variables = variables or {}\n\n    if "user(" in query_string or "user (" in query_string:\n        user_id = variables.get("id", "1")\n        raw_result = resolve_user(None, None, id=user_id)\n        if raw_result is None:\n            return {"data": {"user": None}}\n        requested_fields = _extract_fields(query_string)\n        return {"data": {"user": {field: raw_result.get(field) for field in requested_fields}}}\n\n    if "users" in query_string:\n        raw_results = resolve_users(None, None)\n        requested_fields = _extract_fields(query_string)\n        rows = [{field: raw.get(field) for field in requested_fields} for raw in raw_results]\n        return {"data": {"users": rows}}\n\n    return {"errors": [{"message": "Unknown query"}]}\n\n\ndef _extract_fields(query_string):\n    match = re.search(r"user(?:s)?(?:\\\\([^)]*\\\\))?\\\\s*\\\\{([^{}]+)\\\\}", query_string, re.S)\n    if not match:\n        return SCHEMA_FIELDS.get("User", [])\n    return [field for field in re.split(r"\\\\s+", match.group(1).strip()) if field]\n\n\ndef run_server():\n    query = \'query { user(id: "1") { id userName emailAddress firstName lastName } }\'\n    print(json.dumps(execute_query(query, {"id": "1"}), indent=2))\n\n\nif __name__ == "__main__":\n    run_server()\n', encoding='utf-8')
PYWRITE_2

echo "Fix applied: resolver now returns camelCase keys matching GraphQL schema"
