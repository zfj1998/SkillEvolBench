from __future__ import annotations


LINKED_METADATA_GROUPS = [
    {"department", "title"},
]


def expanded_suppression(explicit_fields: set[str]) -> set[str]:
    suppressed = set(explicit_fields)
    for group in LINKED_METADATA_GROUPS:
        if suppressed & group:
            suppressed |= group
    return suppressed
