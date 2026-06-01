from __future__ import annotations


def choose_join_columns(user_columns: list[str], transaction_columns: list[str]) -> tuple[str, str]:
    for candidate in ("id", "user_id"):
        if candidate in user_columns and candidate in transaction_columns:
            return candidate, candidate
    if "id" in user_columns and "id" in transaction_columns:
        return "id", "id"
    raise KeyError("No compatible join key found")
