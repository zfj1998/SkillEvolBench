from __future__ import annotations


def merge_profile(record, profile):
    merged = dict(record)
    merged.setdefault("timezone", profile.get("timezone"))
    merged.setdefault("currency", profile.get("currency"))
    return merged
