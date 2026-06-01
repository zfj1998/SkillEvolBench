from __future__ import annotations


def heading(title: str) -> str:
    return f"## {title}"


def kv_table(rows: list[tuple[str, str]]) -> str:
    lines = ["| Field | Value |", "| --- | --- |"]
    for key, value in rows:
        lines.append(f"| {key} | {value} |")
    return "\n".join(lines)
