from __future__ import annotations

import json
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
AUDIT = PROJECT_ROOT / "customer_merge_audit.json"


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_source_discovery_mentions_all_three_files():
    text = read_text("source_discovery.py")
    for source_name in ("crm_export.csv", "newsletter_list.csv", "event_attendees.csv"):
        assert source_name in text


def test_pipeline_uses_discovery_and_merge_policy():
    text = read_text("clean_customer_list.py")
    assert "discover_sources" in text and "merge_customer" in text


def test_audit_lists_sources_seen():
    assert AUDIT.exists()
    audit = json.loads(AUDIT.read_text(encoding="utf-8"))
    sources = audit["sources_seen"]
    assert set(sources) == {"crm_export.csv", "newsletter_list.csv", "event_attendees.csv"}
    assert audit["raw_records"] > audit["unique_records"]
    assert audit["dedup_method"] == "normalized email"
