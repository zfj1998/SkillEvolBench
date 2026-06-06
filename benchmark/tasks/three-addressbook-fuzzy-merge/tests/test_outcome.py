"""
T1 outcome tests: three-addressbook-fuzzy-merge
"""
from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
SCRIPT_DIR = Path(__file__).resolve().parent
MASTER = PROJECT_ROOT / "master_contacts.csv"
REPORT = PROJECT_ROOT / "merge_report.md"
AUDIT = PROJECT_ROOT / "merge_audit.json"


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline() -> None:
    subprocess.run([sys.executable, str(PROJECT_ROOT / "build_master_contacts.py")], cwd=PROJECT_ROOT, check=True)


def load_master():
    with MASTER.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_truth():
    return json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))


def _find_row(rows, email):
    for row in rows:
        if (row.get("email") or "").strip().lower() == email:
            return row
    return None


def test_master_file_exists():
    assert MASTER.exists(), f"Expected output file not found: {MASTER}"


def test_report_file_exists():
    assert REPORT.exists(), f"Expected output file not found: {REPORT}"


def test_exact_unique_count():
    truth = load_truth()
    rows = load_master()
    assert len(rows) == truth["total_unique"], f"Expected {truth['total_unique']} unique contacts, got {len(rows)}"


def test_phone_assisted_clusters_are_merged():
    rows = load_master()
    anchors = {
        "robert1@corp.net": ("Robert Jones", {"crm", "hr", "email_contacts"}),
        "james5@biz.org": ("James Wilson", {"crm", "hr", "email_contacts"}),
        "owen40@enterprise.io": ("Owen Roberts", {"crm", "hr", "email_contacts"}),
    }
    for email, (expected_name, expected_sources) in anchors.items():
        row = _find_row(rows, email)
        assert row is not None, f"Expected merged cluster for {email}"
        assert row["name"] == expected_name, f"{email} should keep the most complete name {expected_name}, got {row['name']}"
        assert set(filter(None, row["_sources"].split(","))) == expected_sources, f"{email} should merge all three sources"


def test_false_merge_protection():
    rows = load_master()
    emails = {(row.get("email") or "").strip().lower() for row in rows}
    assert "john.smith.nyc@acme.com" in emails and "john.smith.sf@corp.net" in emails


def test_master_records_are_information_complete():
    rows = load_master()
    complete = sum(1 for row in rows if row["name"] and (row["email"] or row["phone"]))
    assert complete / len(rows) >= 0.95, "Expected at least 95% of master rows to keep identifying information"


def test_audit_exists_and_counts_match():
    assert AUDIT.exists(), "merge_audit.json must exist"
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rows = load_master()
    assert audit["master_records"] == len(rows)
    assert audit["raw_records"] > len(rows)
    truth = load_truth()
    assert audit["phone_assisted_merges"] == len(truth["phone_assisted_ids"])
    assert "phone" in audit["matcher"].lower() and "nickname" in audit["matcher"].lower()
