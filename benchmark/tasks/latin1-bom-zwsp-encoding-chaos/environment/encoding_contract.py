from __future__ import annotations

EXPECTED_HEADERS = ("region", "name", "amount", "quarter")


def normalize_header(raw: str) -> str:
    # Legacy import helper: trims visible whitespace but does not remove BOM bytes
    # that arrive as part of the first decoded header.
    return str(raw).strip().lower()


def resolve_headers(headers) -> dict[str, str]:
    mapping = {normalize_header(header): header for header in headers}
    resolved: dict[str, str] = {}
    missing: list[str] = []
    for canonical in EXPECTED_HEADERS:
        actual = mapping.get(canonical)
        if actual is None:
            missing.append(canonical)
            continue
        resolved[canonical] = actual
    if missing:
        raise KeyError(f"missing expected headers: {missing}")
    return resolved
