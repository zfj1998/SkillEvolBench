from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([os.environ.get("PYTHON_BIN", "python3"), "action_tracker.py"], cwd=PROJECT_ROOT, check=True)

def output():
    path = PROJECT_ROOT / "output" / "actions.json"
    assert path.exists(), "output/actions.json was not created"
    return json.loads(path.read_text(encoding="utf-8"))

def actions_by_id():
    return {action["id"]: action for action in output().get("actions", [])}

class TestOutcome:
    def test_expected_actions_detected(self):
        actual = set(actions_by_id())
        expected = set(GT["expected_action_ids"])
        missing = expected - actual
        assert len(missing) <= GT.get("allowed_missing_actions", 0), f"missing expected actions: {sorted(missing)}"

    def test_no_false_positive_ids(self):
        actual_sources = {action.get("source_message_id") for action in output().get("actions", [])}
        forbidden = set(GT.get("non_action_message_ids", []))
        assert actual_sources.isdisjoint(forbidden), f"non-action messages extracted: {sorted(actual_sources & forbidden)}"

    def test_assignees_deadlines_and_descriptions(self):
        actual = actions_by_id()
        for aid, expected in GT.get("expected_fields", {}).items():
            assert aid in actual, f"missing action {aid}"
            for field in ["assignee", "deadline", "status"]:
                if field in expected:
                    assert actual[aid].get(field) == expected[field], f"{aid}.{field}: {actual[aid].get(field)} != {expected[field]}"
            for word in expected.get("description_terms", []):
                assert word.lower() in actual[aid].get("description", "").lower(), f"{aid} description missing {word}"

    def test_implicit_and_confidence_requirements(self):
        actual = actions_by_id()
        for aid in GT.get("implicit_action_ids", []):
            assert actual.get(aid, {}).get("implicit") is True, f"{aid} should be marked implicit"
        for low, high in GT.get("confidence_less_than", []):
            assert actual[low].get("confidence", 1) < actual[high].get("confidence", 0), f"{low} confidence should be lower than {high}"

    def test_status_counts(self):
        expected = GT.get("expected_status_counts", {})
        if not expected:
            return
        actions = output().get("actions", [])
        actual = {status: sum(1 for action in actions if action.get("status") == status) for status in expected}
        assert actual == expected, f"status counts mismatch: {actual} != {expected}"

    def test_followup_drafts(self):
        expected = GT.get("expected_followups", {})
        if not expected:
            return
        drafts = {draft["action_id"]: draft for draft in output().get("followups", [])}
        assert set(drafts) == set(expected), f"followup draft IDs mismatch: {sorted(drafts)} vs {sorted(expected)}"
        for aid, spec in expected.items():
            body = drafts[aid].get("body", "").lower()
            for term in spec.get("must_include", []):
                assert term.lower() in body, f"followup {aid} missing {term}: {body}"
            for phrase in ["you failed", "overdue.", "this is overdue"]:
                assert phrase not in body, f"followup tone is too accusatory: {body}"
