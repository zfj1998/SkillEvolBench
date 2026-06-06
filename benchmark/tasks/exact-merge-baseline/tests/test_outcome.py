from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
TEST_DIR = Path(__file__).resolve().parent
MASTER = PROJECT_ROOT / "master_employees.csv"
LOG = PROJECT_ROOT / "conflict_log.json"


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline():
    subprocess.run([sys.executable, str(PROJECT_ROOT / "merge_employee_records.py")], cwd=PROJECT_ROOT, check=True)


def load_master():
    with MASTER.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_log():
    return json.loads(LOG.read_text(encoding="utf-8"))


def load_truth():
    return json.loads((TEST_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def test_master_file_exists():
    assert MASTER.exists()


def test_master_has_100_rows():
    assert len(load_master()) == 100


def test_all_employee_ids_present():
    rows = load_master()
    ids = {row["employee_id"] for row in rows}
    assert ids == {f"E{i:03d}" for i in range(1, 101)}


def test_no_duplicate_ids():
    rows = load_master()
    ids = [row["employee_id"] for row in rows]
    assert len(ids) == len(set(ids))


def test_has_fields_from_both_sources():
    sample = load_master()[0]
    for field in ("name", "manager", "location", "salary", "grade", "start_date"):
        assert field in sample


def test_conflict_log_captures_most_known_conflicts():
    truth = load_truth()
    log = load_log()
    assert log["total_conflicts"] == truth["conflict_count"], f"Expected all {truth['conflict_count']} known conflicts to be logged"
    assert log["summary"]["review_queue_size"] == truth["conflict_count"]
    assert log["summary"]["field_counts"]["dept"] == truth["conflict_count"]


def test_conflict_log_covers_all_expected_employee_ids():
    truth = load_truth()
    log = load_log()
    logged_ids = {entry["employee_id"] for entry in log["conflicts"]}
    truth_ids = {entry["id"] for entry in truth["conflicts"]}
    assert logged_ids == truth_ids


def test_conflict_entries_include_resolution_policy_field():
    log = load_log()
    for entry in log["conflicts"]:
        assert entry["resolved_by"], "conflict entry must record which source resolved the conflict"
        assert entry["resolved_to"] in {entry["employees_value"], entry["salaries_value"]}


def test_conflict_entries_include_merge_key_and_source_priority():
    log = load_log()
    for entry in log["conflicts"]:
        assert entry.get("merge_key") == "employee_id"
        assert isinstance(entry.get("source_priority"), str) and entry["source_priority"]
