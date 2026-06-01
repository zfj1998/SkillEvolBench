from __future__ import annotations

from profile_defaults import SYSTEM_DEFAULTS


def fill_system_defaults(record):
    merged = dict(record)
    if merged.get("currency") is None:
        merged["currency"] = SYSTEM_DEFAULTS["currency"]
    return merged
