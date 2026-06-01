from __future__ import annotations


def build_summary(conflicts: list[dict]) -> dict:
    field_counts: dict[str, int] = {}
    for conflict in conflicts:
        field = conflict.get("field", "")
        field_counts[field] = field_counts.get(field, 0) + 1
    return {
        "review_queue_size": len(conflicts),
        "field_counts": field_counts,
    }
