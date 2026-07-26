from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
TASK_ROOT = SCRIPT_DIR.parent
GT = json.loads((Path(__file__).resolve().parent / "ground_truth.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([os.environ.get("PYTHON_BIN", "python3"), "triage_pipeline.py"], cwd=PROJECT_ROOT, check=True)

def load_output():
    path = PROJECT_ROOT / "output" / "triage.json"
    assert path.exists(), "output/triage.json was not created"
    return json.loads(path.read_text(encoding="utf-8"))

def by_id(output):
    return {item["id"]: item for item in output.get("items", [])}

class TestOutcome:
    def test_all_messages_are_classified_once(self):
        output = load_output()
        items = output.get("items", [])
        expected_ids = set(GT["expected_priorities"])
        assert len(items) == len(expected_ids), f"expected {len(expected_ids)} classified messages, got {len(items)}"
        assert {item.get("id") for item in items} == expected_ids, "classified IDs do not match mailbox"

    def test_priority_counts_match_expected_distribution(self):
        output = load_output()
        expected_counts = {priority: list(GT["expected_priorities"].values()).count(priority) for priority in ["P0", "P1", "P2", "P3"]}
        actual_counts = {priority: sum(1 for item in output.get("items", []) if item.get("priority") == priority) for priority in ["P0", "P1", "P2", "P3"]}
        assert actual_counts == expected_counts, f"priority count mismatch: actual={actual_counts} expected={expected_counts}"
        summary_counts = output.get("summary", {}).get("counts", {})
        assert all(summary_counts.get(priority) == expected_counts[priority] for priority in expected_counts), f"summary counts do not match expected: {summary_counts}"

    def test_key_priorities_are_correct(self):
        output = load_output()
        actual = by_id(output)
        checks = GT.get("key_priority_checks") or GT["expected_priorities"]
        wrong = {mid: (actual.get(mid, {}).get("priority"), expected) for mid, expected in checks.items() if actual.get(mid, {}).get("priority") != expected}
        assert not wrong, f"priority mismatches: {wrong}"

    def test_p0_set_matches_ground_truth(self):
        output = load_output()
        actual_p0 = {item["id"] for item in output["items"] if item.get("priority") == "P0"}
        expected_p0 = set(GT.get("expected_p0", []))
        if expected_p0:
            assert actual_p0 == expected_p0, f"P0 mismatch: actual={sorted(actual_p0)} expected={sorted(expected_p0)}"

    def test_p3_set_matches_when_specified(self):
        expected_p3 = set(GT.get("expected_p3", []))
        if not expected_p3:
            return
        output = load_output()
        actual_p3 = {item["id"] for item in output["items"] if item.get("priority") == "P3"}
        assert expected_p3.issubset(actual_p3), f"expected P3 items missing: {sorted(expected_p3 - actual_p3)}"

    def test_rank_constraints(self):
        output = load_output()
        actual = by_id(output)
        for higher, lower in GT.get("rank_before", []):
            assert actual[higher]["rank"] < actual[lower]["rank"], f"{higher} should rank before {lower}"

    def test_response_list_when_expected(self):
        if "expected_response_ids" not in GT:
            return
        expected = set(GT["expected_response_ids"])
        output = load_output()
        actual = set(output.get("response_list", []))
        assert actual == expected, f"response list mismatch: actual={sorted(actual)} expected={sorted(expected)}"

    def test_reasons_are_present_and_nontrivial(self):
        output = load_output()
        invalid = {
            item.get("id"): item.get("reason")
            for item in output.get("items", [])
            if len(str(item.get("reason", "")).split()) < 3
        }
        assert not invalid, f"each classification needs a brief rationale: {invalid}"

    def test_p0_drafts_when_expected(self):
        expected = GT.get("expected_drafts", {})
        if not expected:
            return
        output = load_output()
        drafts = {draft["email_id"]: draft for draft in output.get("drafts", [])}
        assert set(drafts) == set(expected), f"draft IDs mismatch: {sorted(drafts)} vs {sorted(expected)}"
        for mid, spec in expected.items():
            body = drafts[mid].get("body", "").lower()
            for keyword in spec.get("must_include", []):
                assert keyword.lower() in body, f"draft for {mid} missing {keyword!r}: {body}"
