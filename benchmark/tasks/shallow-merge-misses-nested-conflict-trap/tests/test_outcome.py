from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
PROJECT = Path(__file__).resolve().parent.parent / "project"
REPORT = PROJECT_ROOT / "reconciliation_report.json"


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline():
    subprocess.run([sys.executable, str(PROJECT_ROOT / "reconcile_nested_differences.py")], cwd=PROJECT_ROOT, check=True)


def load_report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def load_truth():
    return {
        "conflicts": [
            {"record_id": "R002", "field_path": "address.street"},
            {"record_id": "R002", "field_path": "address.zip"},
            {"record_id": "R005", "field_path": "compensation.bonus"},
            {"record_id": "R007", "field_path": "phone.mobile"},
            {"record_id": "R009", "field_path": "address.street"},
            {"record_id": "R009", "field_path": "address.zip"},
            {"record_id": "R009", "field_path": "compensation.bonus"},
        ]
    }


def test_report_exists():
    assert REPORT.exists()


def test_report_is_not_zero_differences():
    report = load_report()
    assert report["total_differences"] > 0, "Report must not claim zero differences"


def test_minimum_three_nested_conflicts():
    truth = load_truth()
    text = json.dumps(load_report()).lower()
    found = sum(1 for conflict in truth["conflicts"] if conflict["record_id"].lower() in text and conflict["field_path"].lower() in text)
    assert found >= 5, f"Expected at least 5 of 7 nested conflicts, got {found}"


def test_nested_paths_in_output():
    text = json.dumps(load_report()).lower()
    for path in ("address.street", "address.zip", "compensation.bonus", "phone.mobile"):
        assert path in text


def test_each_difference_has_source_a_and_source_b_values():
    differences = load_report()["differences"]
    assert differences
    for entry in differences:
        assert "record_id" in entry
        assert "path" in entry
        assert "source_a" in entry
        assert "source_b" in entry
        assert entry["source_a"] != entry["source_b"]
