from __future__ import annotations


def department_title_alignment(department: str, title: str, missing_marker: str) -> bool:
    if department in ("", missing_marker) or title in ("", missing_marker):
        return True
    return department.split()[0].lower() in title.lower()
