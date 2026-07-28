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

def actions_by_source():
    actions = output().get("actions", [])
    by_source = {action.get("source_message_id"): action for action in actions}
    assert len(by_source) == len(actions), "source_message_id must identify each action"
    return by_source

class TestOutcome:
    def test_expected_actions_detected(self):
        actual = set(actions_by_source())
        expected = {
            spec["source_message_id"]
            for spec in GT.get("expected_fields", {}).values()
        }
        missing = expected - actual
        assert len(missing) <= GT.get("allowed_missing_actions", 0), f"missing expected actions: {sorted(missing)}"

    def test_no_false_positive_ids(self):
        actual_sources = {action.get("source_message_id") for action in output().get("actions", [])}
        forbidden = set(GT.get("non_action_message_ids", []))
        assert actual_sources.isdisjoint(forbidden), f"non-action messages extracted: {sorted(actual_sources & forbidden)}"

    def test_assignees_deadlines_and_descriptions(self):
        actual = actions_by_source()
        for aid, expected in GT.get("expected_fields", {}).items():
            source_id = expected["source_message_id"]
            assert source_id in actual, f"missing action from {source_id} ({aid})"
            item = actual[source_id]
            if "allowed_assignees" in expected:
                assert str(item.get("assignee", "")).lower() in {
                    value.lower() for value in expected["allowed_assignees"]
                }, f"{source_id}.assignee: {item.get('assignee')}"
            elif "assignee" in expected:
                assert item.get("assignee") == expected["assignee"], (
                    f"{source_id}.assignee: {item.get('assignee')} "
                    f"!= {expected['assignee']}"
                )
            for field in ["deadline", "status"]:
                if field in expected:
                    assert item.get(field) == expected[field], f"{source_id}.{field}: {item.get(field)} != {expected[field]}"
            for word in expected.get("description_terms", []):
                assert word.lower() in item.get("description", "").lower(), f"{source_id} description missing {word}"

    def test_implicit_and_confidence_requirements(self):
        actual = actions_by_source()
        for aid in GT.get("implicit_action_ids", []):
            source_id = GT["expected_fields"][aid]["source_message_id"]
            assert actual.get(source_id, {}).get("implicit") is True, f"{source_id} should be marked implicit"
        for low, high in GT.get("confidence_less_than", []):
            low_source = GT["expected_fields"][low]["source_message_id"]
            high_source = GT["expected_fields"][high]["source_message_id"]
            assert actual[low_source].get("confidence", 1) < actual[high_source].get("confidence", 0), f"{low_source} confidence should be lower than {high_source}"

    def test_status_counts(self):
        expected = GT.get("expected_status_counts", {})
        if not expected:
            return
        actions = output().get("actions", [])
        actual = {status: sum(1 for action in actions if action.get("status") == status) for status in expected}
        assert actual == expected, f"status counts mismatch: {actual} != {expected}"

    def test_summary_object_matches_actions(self):
        data = output()
        summary = data.get("summary")
        assert isinstance(summary, dict), "summary object is required"
        actions = data.get("actions", [])
        assert summary.get("total_actions") == len(actions), "summary.total_actions must match extracted actions"
        for status, expected_count in GT.get("expected_status_counts", {}).items():
            assert summary.get(status) == expected_count, f"summary.{status} mismatch"

    def test_followup_drafts(self):
        expected = GT.get("expected_followups", {})
        if not expected:
            return
        id_to_source = {
            action["id"]: action.get("source_message_id")
            for action in output().get("actions", [])
        }
        drafts = {
            id_to_source.get(draft["action_id"]): draft
            for draft in output().get("followups", [])
        }
        expected_sources = {
            spec["source_message_id"] for spec in expected.values()
        }
        assert set(drafts) == expected_sources, f"followup source IDs mismatch: {sorted(drafts)} vs {sorted(expected_sources)}"
        for aid, spec in expected.items():
            body = drafts[spec["source_message_id"]].get("body", "").lower()
            for term in spec.get("must_include", []):
                assert term.lower() in body, f"followup {aid} missing {term}: {body}"
            for phrase in ["you failed", "overdue.", "this is overdue"]:
                assert phrase not in body, f"followup tone is too accusatory: {body}"
