from __future__ import annotations


def summarize_row_counts(row_counts: dict[str, int]) -> list[dict[str, object]]:
    issues = []
    for table, count in row_counts.items():
        if count <= 0:
            issues.append({"kind": "empty_table", "source": table, "detail": f"{table} has no rows", "impact": "high"})
    return issues
