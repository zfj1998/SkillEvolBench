from __future__ import annotations

from collections import Counter


# Starter bug: title disagreements are treated as linked metadata and suppressed
# instead of being surfaced as explicit conflicts.
SUPPRESS_CONFLICT_FIELDS = {"title"}


def majority_value(values):
    present = [value for value in values if value not in ("", None)]
    if not present:
        return ""
    return Counter(present).most_common(1)[0][0]
