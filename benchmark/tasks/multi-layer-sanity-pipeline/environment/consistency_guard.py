from __future__ import annotations


def allocation_consistent(project_total: float, allocation_total: float) -> bool:
    return abs(project_total - allocation_total) <= 0.1
