from __future__ import annotations


def compute_total_compensation(base_salary: int | str, bonus: int | str) -> str:
    # Starter bug: ignores bonus even though the template requires total compensation.
    return str(int(base_salary or 0))
