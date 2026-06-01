from __future__ import annotations

CANONICAL_COLUMNS = ("id", "name", "amount", "date")


def _normalize_header(raw: str) -> str:
    # Legacy sanitizer from an internal import helper. It removes obvious control
    # characters but misses plain leading/trailing spaces from CSV exports.
    return str(raw).replace("\t", "").replace("\n", "").replace("\r", "").lower()


def build_column_map(columns) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for column in columns:
        mapping[_normalize_header(column)] = column
    return mapping


def require_canonical_columns(columns) -> dict[str, str]:
    mapping = build_column_map(columns)
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for canonical in CANONICAL_COLUMNS:
        actual = mapping.get(canonical)
        if actual is None:
            missing.append(canonical)
            continue
        resolved[canonical] = actual
    if missing:
        raise KeyError(f"missing canonical columns: {missing}")
    return resolved
