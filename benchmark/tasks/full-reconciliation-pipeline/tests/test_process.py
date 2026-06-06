from __future__ import annotations

import json
import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
LOG = PROJECT_ROOT / "conflict_log.json"


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_entity_matcher_supports_phone_and_email():
    text = read_text("entity_matcher.py")
    assert "normalize_phone" in text and "normalize_email" in text


def test_entity_matcher_handles_comma_name_variants():
    text = read_text("entity_matcher.py")
    assert "split(\",\", 1)" in text or "f\"{right} {left}\"" in text, "matcher should normalize 'Last, First' records before fuzzy comparison"


def test_entity_matcher_has_phone_nickname_fallback():
    text = read_text("entity_matcher.py")
    assert "nickname_map" in text or "bobby" in text, "matcher should encode nickname aliases for fuzzy matching"
    assert "left_phone" in text and "right_phone" in text, "matcher should use phone fallback when email is missing"


def test_pipeline_uses_matcher_and_conflict_reporter():
    text = read_text("run_full_reconciliation.py")
    assert "same_entity" in text and "deep_diff" in text and "choose_value" in text


def test_conflict_log_mentions_matching_method():
    text = json.dumps(json.loads(LOG.read_text(encoding="utf-8"))).lower()
    assert "matching_method" in text
