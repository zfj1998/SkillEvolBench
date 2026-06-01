from __future__ import annotations

from collections import defaultdict


def collect_duplicate_batches(rows: list[dict[str, object]]) -> dict[str, list[str]]:
    grouped: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        batch_id = str(row["batch_id"])
        grouped[batch_id].append(batch_id)
    return {batch_id: ids for batch_id, ids in grouped.items() if len(ids) > 1}
