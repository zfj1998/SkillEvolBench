from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_deep_compare_is_recursive():
    text = read_text("deep_compare.py")
    assert "deep_diff(" in text and "isinstance(left, dict)" in text


def test_orchestrator_does_not_rely_on_top_level_gate():
    text = read_text("reconcile_nested_differences.py")
    assert "deep_diff" in text
    assert "should_skip_nested_diff" not in text
