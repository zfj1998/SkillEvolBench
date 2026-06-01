from __future__ import annotations


def build_quality_note(missing_days: list[str]) -> tuple[str, str]:
    if not missing_days:
        return "complete", "March data coverage looks complete."
    if len(missing_days) <= 1:
        return "complete_enough", f"{len(missing_days)} day is missing from the source export."
    return "incomplete", f"{len(missing_days)} days are missing from the source export."
