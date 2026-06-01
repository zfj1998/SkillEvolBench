from __future__ import annotations


def annotate_groups(differences: list[dict]) -> list[dict]:
    grouped = []
    for difference in differences:
        group = "compensation" if difference["path"].startswith("compensation.") else "address"
        enriched = dict(difference)
        enriched["group"] = group
        grouped.append(enriched)
    return grouped
