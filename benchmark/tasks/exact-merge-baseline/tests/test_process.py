from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_exact_join_uses_employee_id():
    text = read_text("exact_join.py")
    assert "employee_id" in text


def test_conflict_log_policy_keeps_both_values():
    text = read_text("conflict_policy.py")
    assert "employees_value" in text and "salaries_value" in text and "resolved_to" in text


def test_conflict_policy_does_not_trim_review_queue():
    text = read_text("conflict_policy.py")
    assert "[:12]" not in text and "first 12" not in text and "review items" not in text


def test_pipeline_writes_conflict_log():
    text = read_text("merge_employee_records.py")
    assert "conflict_log.json" in text and "source_priority" in text and "build_summary" in text
