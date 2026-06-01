from __future__ import annotations


def index_by_employee_id(rows: list[dict]) -> dict[str, dict]:
    return {row["employee_id"]: row for row in rows}


def join_exact(left_rows: list[dict], right_rows: list[dict]) -> list[tuple[dict, dict]]:
    right_index = index_by_employee_id(right_rows)
    pairs = []
    for row in left_rows:
        pairs.append((row, right_index.get(row["employee_id"], {})))
    return pairs
