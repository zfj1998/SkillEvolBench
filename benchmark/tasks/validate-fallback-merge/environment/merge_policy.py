from __future__ import annotations


def merge_records(primary_records: list[dict], invalid_ids: set[int], fetch_backup) -> list[dict]:
    merged = []
    for record in primary_records:
        if record["id"] in invalid_ids:
            merged.append(fetch_backup(record["id"]))
        else:
            merged.append(record)
    return merged
