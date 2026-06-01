from __future__ import annotations

from collections import Counter


def majority_value(values):
    present = [value for value in values if value not in ("", None)]
    if not present:
        return ""
    return Counter(present).most_common(1)[0][0]
