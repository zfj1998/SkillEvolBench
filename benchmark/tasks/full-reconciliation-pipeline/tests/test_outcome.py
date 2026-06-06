from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
PROJECT = Path(__file__).resolve().parent.parent / "project"
MASTER = PROJECT_ROOT / "master_dataset.json"
LOG = PROJECT_ROOT / "conflict_log.json"
EXPECTED_TOTAL_UNIQUE = 220
PHONE_ASSISTED_IDS = ("P018", "P041", "P066", "P098", "P103")


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline():
    subprocess.run([sys.executable, str(PROJECT_ROOT / "run_full_reconciliation.py")], cwd=PROJECT_ROOT, check=True)


def load_master():
    return json.loads(MASTER.read_text(encoding="utf-8"))


def load_log():
    return json.loads(LOG.read_text(encoding="utf-8"))


def _find_by_record_id(master, record_id):
    for row in master:
        if record_id in row.get("_record_ids", []):
            return row
    return None


def test_master_exists():
    assert MASTER.exists()


def test_conflict_log_exists():
    assert LOG.exists()


def test_correct_unique_count():
    master = load_master()
    assert len(master) == EXPECTED_TOTAL_UNIQUE, f"Expected {EXPECTED_TOTAL_UNIQUE} merged records, got {len(master)}"


def test_phone_assisted_records_are_merged():
    master = load_master()
    for record_id in PHONE_ASSISTED_IDS:
        row = _find_by_record_id(master, record_id)
        assert row is not None, f"Expected merged row for {record_id}"
        assert len(row["_sources"]) >= 2, f"{record_id} should merge across multiple systems"


def test_master_records_include_scalar_winner_fields():
    master = load_master()
    assert master
    for row in master[:20]:
        for field in ("record_id", "name", "email", "phone", "department"):
            winner_field = f"_{field}_winner"
            assert winner_field in row
            assert row[winner_field] in row["_sources"]


def test_nested_conflicts_in_log():
    text = json.dumps(load_log()).lower()
    for path in ("address.street", "address.zip", "compensation.bonus"):
        assert path in text


def test_conflict_log_has_resolution():
    log = load_log()
    assert "resolution_strategy" in log and "system_a" in log["resolution_strategy"]


def test_matching_method_mentions_phone_fallback():
    log = load_log()
    text = log.get("matching_method", "").lower()
    assert "phone" in text and "nickname" in text
