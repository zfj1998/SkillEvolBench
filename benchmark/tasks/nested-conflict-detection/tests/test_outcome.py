from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
TEST_DIR = Path(__file__).resolve().parent
REPORT = PROJECT_ROOT / "differences_report.json"


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline():
    subprocess.run([sys.executable, str(PROJECT_ROOT / "build_differences_report.py")], cwd=PROJECT_ROOT, check=True)


def load_report():
    return json.loads(REPORT.read_text(encoding="utf-8"))


def load_truth():
    return json.loads((TEST_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_report_exists():
    assert REPORT.exists()


def test_detects_all_nested_conflicts():
    report = load_report()
    truth = load_truth()
    text = json.dumps(report).lower()
    found = sum(1 for conflict in truth["conflicts"] if conflict["employee_id"].lower() in text and conflict["field_path"].lower() in text)
    assert found >= 11, f"Expected at least 11 of 12 nested conflicts, got {found}"


def test_dot_notation_paths_present():
    text = json.dumps(load_report()).lower()
    for path in ("address.street", "address.zip", "compensation.bonus"):
        assert path in text


def test_matching_fields_not_flagged():
    diffs = load_report()["differences"]
    bad = [entry for entry in diffs if entry["path"] in {"employee_id", "name", "status"}]
    assert not bad


def test_address_conflicts_grouped():
    diffs = load_report()["differences"]
    address_groups = [entry for entry in diffs if entry["group"] == "address"]
    assert len(address_groups) >= 6


def test_each_difference_has_both_source_values():
    diffs = load_report()["differences"]
    assert diffs
    for entry in diffs:
        assert "hr" in entry
        assert "finance" in entry
        assert entry["hr"] != entry["finance"]
