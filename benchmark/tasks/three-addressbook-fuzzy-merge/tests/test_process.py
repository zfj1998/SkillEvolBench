"""
T1 process tests: verify fuzzy merge methodology instead of output-only shortcuts.
"""
from __future__ import annotations

import os
from pathlib import Path


PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))


def read_text(name: str) -> str:
    return (PROJECT_ROOT / name).read_text(encoding="utf-8").lower()


def test_identity_matcher_normalizes_phone():
    text = read_text("identity_matcher.py")
    assert "normalize_phone" in text and "\\d" in text, "identity matcher should normalize phone values before matching"


def test_identity_matcher_has_nickname_logic():
    text = read_text("identity_matcher.py")
    assert "nickname_map" in text or "bob" in text or "jim" in text, "matcher should encode nickname/canonical name handling"


def test_identity_matcher_supports_initial_fallback():
    text = read_text("identity_matcher.py")
    assert "[:1]" in text or "initial" in text, "matcher should support initial-aware fallback for fuzzy phone matches"


def test_merge_policy_canonicalizes_last_first_names():
    text = read_text("merge_policy.py")
    assert "_canonicalize_name" in text or "split(\",\", 1)" in text, "merge policy should normalize 'Last, First' names before choosing a canonical display value"


def test_pipeline_uses_matcher_and_merge_policy():
    text = read_text("build_master_contacts.py")
    assert "same_person" in text and "merge_cluster" in text, "pipeline should delegate to matcher and merge policy helpers"


def test_report_mentions_false_merge_protection():
    report = PROJECT_ROOT / "merge_report.md"
    assert report.exists(), "merge_report.md must exist"
    text = report.read_text(encoding="utf-8").lower()
    assert "john smith" in text
    assert any(marker in text for marker in ["same-name", "false merges", "false merge", "distinct"]), "report should document same-name false merge protection"
