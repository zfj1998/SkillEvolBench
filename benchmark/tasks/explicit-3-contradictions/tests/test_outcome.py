from __future__ import annotations
import json
import subprocess
import sys
from pathlib import Path

import os

TASK_ROOT = Path(__file__).resolve().parents[1]
ROOT = Path(os.environ.get("PROJECT_ROOT", TASK_ROOT)).resolve()
OUTPUT = ROOT / "output" / "consistency_audit.json"
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))
SCHEMA = json.loads((ROOT / "schemas" / "output_schema.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([sys.executable, "audit_pipeline.py"], cwd=ROOT, check=True)

def audit():
    return json.loads(OUTPUT.read_text(encoding="utf-8"))

def by_pair():
    return {item["pair_id"]: item for item in audit()["results"]}

class TestOutcome:
    def test_output_exists(self):
        assert OUTPUT.exists()

    def test_output_matches_documented_schema(self):
        data = audit()
        for field in SCHEMA["required"]:
            assert field in data, f"missing schema-required field {field}"
        assert isinstance(data["checked_pairs"], int)
        assert isinstance(data["contradictions"], list)
        assert isinstance(data["results"], list)
        result_required = set(SCHEMA["properties"]["results"]["items"]["required"])
        contradiction_required = set(SCHEMA["properties"]["contradictions"]["items"]["required"])
        for item in data["results"]:
            assert result_required.issubset(item), f"result missing fields: {result_required - set(item)}"
            assert isinstance(item["pair_id"], str)
            assert isinstance(item["label"], str)
            assert isinstance(item["type"], str)
            assert isinstance(item["reason"], str)
        for item in data["contradictions"]:
            assert contradiction_required.issubset(item), f"contradiction missing fields: {contradiction_required - set(item)}"
            assert isinstance(item["evidence"], list)
            assert all(isinstance(text, str) for text in item["evidence"])

    def test_all_pairs_checked(self):
        assert audit()["checked_pairs"] == len(GT["labels"])

    def test_true_contradictions_detected(self):
        results = by_pair()
        for pair_id in GT["true_ids"]:
            assert results[pair_id]["label"] == "contradiction", pair_id

    def test_exact_contradiction_count(self):
        assert len(audit()["contradictions"]) == len(GT["true_ids"])

    def test_exact_contradiction_ids(self):
        found = {item["pair_id"] for item in audit()["contradictions"]}
        assert found == set(GT["true_ids"])

    def test_false_contradictions_not_flagged(self):
        results = by_pair()
        for pair_id in GT["false_ids"]:
            assert results[pair_id]["label"] != "contradiction", pair_id

    def test_required_types_present(self):
        types = {item["type"] for item in audit()["contradictions"]}
        for expected in GT["required_types"]:
            assert expected in types, expected

    def test_evidence_quotes_present(self):
        for item in audit()["contradictions"]:
            assert len(item["evidence"]) == 2
            assert all(len(text) > 20 for text in item["evidence"])

    def test_reasoning_is_specific(self):
        for pair_id in GT["true_ids"]:
            reason = by_pair()[pair_id]["reason"].lower()
            assert any(term in reason for term in ["same", "incompatible", "conflict", "continuous", "summary", "scope", "year", "denied"])

    def test_no_unchecked_placeholder_labels(self):
        assert all(item["type"] != "unchecked" for item in audit()["results"])

    def test_provenance_is_preserved(self):
        for item in audit()["results"]:
            provenance = item.get("provenance", {})
            assert provenance.get("evidence_sources"), "missing evidence source provenance"
            assert provenance.get("source_urls"), "missing source URL provenance"
            assert provenance.get("source_cards_chars", 0) > 100, "source cards were not loaded"
