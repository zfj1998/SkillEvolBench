"""Small GraphQL-style field resolution helpers."""


def resolve_selected_fields(raw_result, requested_fields):
    resolved = {}
    for field in requested_fields:
        resolved[field] = raw_result.get(field)
    return resolved
