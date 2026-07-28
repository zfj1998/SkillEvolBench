from __future__ import annotations

import json
import csv
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
AUDIT = PROJECT_ROOT / "customer_merge_audit.json"
OUTPUT = PROJECT_ROOT / "customer_list.csv"


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_source_discovery_mentions_all_three_files():
    sources = set(json.loads(AUDIT.read_text(encoding="utf-8"))["sources_seen"])
    for source_name in ("crm_export.csv", "newsletter_list.csv", "event_attendees.csv"):
        assert source_name in sources


def test_pipeline_uses_discovery_and_merge_policy():
    rows = list(csv.DictReader(OUTPUT.open(encoding="utf-8", newline="")))
    emails = [row["email"].strip().lower() for row in rows]
    assert rows and len(emails) == len(set(emails))


def test_audit_lists_sources_seen():
    assert AUDIT.exists()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    sources = audit["sources_seen"]
    assert set(sources) == {"crm_export.csv", "newsletter_list.csv", "event_attendees.csv"}
    assert audit["raw_records"] > audit["unique_records"]
    assert audit["dedup_method"] == "normalized email"
