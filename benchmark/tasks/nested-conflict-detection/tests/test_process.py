from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_recursive_diff_exists():
    text = read_text("nested_diff.py")
    assert "deep_diff(" in text and "isinstance(left, dict)" in text


def test_report_builder_uses_grouping():
    text = read_text("build_differences_report.py")
    assert "annotate_groups" in text and "employee_id" in text


def test_grouping_tracks_address_and_compensation():
    text = read_text("conflict_grouping.py")
    assert "compensation" in text and "address" in text
