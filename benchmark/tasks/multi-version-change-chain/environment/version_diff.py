from __future__ import annotations

import re
from itertools import zip_longest


def extract_sections(text: str) -> list[dict[str, str]]:
    sections: list[dict[str, str]] = []

    effective_match = re.search(r"\*\*Effective Date:\*\*\s*(.+)", text)
    if effective_match:
        sections.append(
            {
                "id": "header.effective_date",
                "title": "Header: Effective Date",
                "body": effective_match.group(1).strip(),
            }
        )

    matches = re.findall(r"(?ms)^##\s+([^\n]+)\n\n(.*?)(?=^##\s+|\Z)", text)
    for title, body in matches:
        normalized_title = re.sub(r"^\d+\.\s*", "", title.strip())
        sections.append(
            {
                "id": title.strip(),
                "title": normalized_title,
                "body": body.strip(),
            }
        )
    return sections


def diff_round(old_sections: list[dict[str, str]], new_sections: list[dict[str, str]]) -> list[dict[str, str]]:
    changes: list[dict[str, str]] = []
    for old, new in zip_longest(old_sections, new_sections):
        if old and new:
            if old["body"] != new["body"]:
                changes.append(
                    {
                        "section": old["title"],
                        "kind": "modified",
                        "old": old["body"],
                        "new": new["body"],
                    }
                )
        elif old and not new:
            changes.append({"section": old["title"], "kind": "deleted", "old": old["body"], "new": ""})
        elif new and not old:
            changes.append({"section": new["title"], "kind": "added", "old": "", "new": new["body"]})
    return changes
