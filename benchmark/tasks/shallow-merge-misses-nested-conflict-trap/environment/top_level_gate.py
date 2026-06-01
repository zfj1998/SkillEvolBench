from __future__ import annotations


TOP_LEVEL_FIELDS = ("id", "name", "dept", "status")


def should_skip_nested_diff(left: dict, right: dict) -> bool:
    return all(left.get(field) == right.get(field) for field in TOP_LEVEL_FIELDS)
