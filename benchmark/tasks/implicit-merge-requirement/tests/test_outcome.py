from __future__ import annotations

import csv
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
PROJECT = Path(__file__).resolve().parent.parent / "project"
OUTPUT = PROJECT_ROOT / "customer_list.csv"
AUDIT = PROJECT_ROOT / "customer_merge_audit.json"


@pytest.fixture(scope="session", autouse=True)
def _run_pipeline():
    subprocess.run([sys.executable, str(PROJECT_ROOT / "clean_customer_list.py")], cwd=PROJECT_ROOT, check=True)


def load_rows():
    with OUTPUT.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_truth():
    return json.loads((PROJECT / "ground_truth.json").read_text(encoding="utf-8"))


def test_output_exists():
    assert OUTPUT.exists()


def test_output_columns_match_contract():
    assert set(load_rows()[0]) == {"email", "name", "phone", "city", "company", "tag", "_sources"}


def test_count_at_least_700():
    assert len(load_rows()) >= 700


def test_no_duplicate_emails():
    rows = load_rows()
    emails = [row["email"] for row in rows]
    assert len(emails) == len(set(emails))


def test_coverage_of_all_sources():
    truth = load_truth()
    rows = load_rows()
    known = {email.strip().lower() for email in truth["all_emails"] if email}
    master = {row["email"].strip().lower() for row in rows}
    coverage = len(known & master) / len(known)
    assert coverage >= 0.9, f"Expected at least 90% coverage of known emails, got {coverage:.0%}"


def test_records_have_name_and_email():
    rows = load_rows()
    complete = sum(1 for row in rows if row["email"] and row["name"])
    assert complete / len(rows) >= 0.85


def test_audit_counts_and_source_names_are_correct():
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    rows = load_rows()
    truth = load_truth()
    source_names = {"crm_export.csv", "newsletter_list.csv", "event_attendees.csv"}
    listed = set(audit["sources_seen"])
    assert listed == source_names
    assert audit["unique_records"] == len(rows)
    assert audit["raw_records"] >= len(truth["all_emails"])
    assert audit["dedup_method"]
