from __future__ import annotations


def assess_claim(title: str, draft_text: str, published_text: str) -> tuple[str, str]:
    if draft_text == published_text:
        return "accurate", "No change detected."
    return "changed", "Text differs between draft and published versions."
