from __future__ import annotations


def classify_confidence(issue_count: int) -> str:
    if issue_count == 0:
        return "high"
    return "medium"
