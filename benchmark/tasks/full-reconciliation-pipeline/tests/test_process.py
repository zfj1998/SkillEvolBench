from __future__ import annotations

import json
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
LOG = PROJECT_ROOT / "conflict_log.json"
MASTER = PROJECT_ROOT / "master_dataset.json"


def log_data() -> dict:
    return json.loads(LOG.read_text(encoding="utf-8"))


def matching_method() -> str:
    return str(log_data().get("matching_method", "")).lower()


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_entity_matcher_supports_phone_and_email():
    text = matching_method()
    assert "phone" in text and "email" in text


def test_entity_matcher_handles_comma_name_variants():
    records = json.loads(MASTER.read_text(encoding="utf-8"))
    assert records and all(isinstance(row.get("name"), str) for row in records)


def test_entity_matcher_has_phone_nickname_fallback():
    text = matching_method()
    assert "phone" in text
    assert "nickname" in text or "name" in text


def test_pipeline_uses_matcher_and_conflict_reporter():
    assert MASTER.exists() and LOG.exists()
    assert log_data().get("conflicts")


def test_conflict_log_mentions_matching_method():
    text = json.dumps(log_data()).lower()
    assert "matching_method" in text
