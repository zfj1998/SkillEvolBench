from __future__ import annotations


def deduplicate_rows(rows: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    deduped: list[dict] = []
    for row in rows:
        key = (
            row["channel"],
            row["impressions"],
            row["clicks"],
            row["conversions"],
        )
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    return deduped
