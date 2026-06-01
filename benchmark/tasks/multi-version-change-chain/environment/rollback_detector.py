from __future__ import annotations


def identify_rollbacks(
    v1_sections: list[dict[str, str]],
    v2_changes: list[dict[str, str]],
    v3_changes: list[dict[str, str]],
) -> list[dict[str, str]]:
    v1_by_title = {section["title"]: section["body"] for section in v1_sections}
    round2_by_title = {change["section"]: change for change in v3_changes}
    rollbacks: list[dict[str, str]] = []
    for change in v2_changes:
        follow_up = round2_by_title.get(change["section"])
        if not follow_up:
            continue
        if follow_up.get("new", "") == v1_by_title.get(change["section"], ""):
            rollbacks.append({"section": change["section"], "change": change})
    return rollbacks


def net_changes(v1_sections: list[dict[str, str]], v3_sections: list[dict[str, str]]) -> list[dict[str, str]]:
    v1_by_title = {section["title"]: section["body"] for section in v1_sections}
    v3_by_title = {section["title"]: section["body"] for section in v3_sections}
    changes: list[dict[str, str]] = []
    for title in dict.fromkeys([*v1_by_title.keys(), *v3_by_title.keys()]):
        if v1_by_title.get(title, "") != v3_by_title.get(title, ""):
            changes.append(
                {
                    "section": title,
                    "old": v1_by_title.get(title, ""),
                    "new": v3_by_title.get(title, ""),
                }
            )
    return changes
