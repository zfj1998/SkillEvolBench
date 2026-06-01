from __future__ import annotations

import re


def find_numeric_evidence(text: str) -> list[str]:
    return re.findall(r"\b(?:\d+%|\d+ users|\d+ customers|\$[\d\.]+ million|\d+ days)\b", text)
