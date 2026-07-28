from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task"))
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])


def setup_module() -> None:
    subprocess.run(["python3", "thread_parser.py"], cwd=PROJECT_ROOT, check=True)


def load_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def output() -> dict:
    path = PROJECT_ROOT / "output" / "thread_actions.json"
    assert path.exists(), "output/thread_actions.json was not created"
    return load_json(path)


def config() -> dict:
    return load_json(SCRIPT_DIR / "test_config.json")


def expected_actions() -> dict:
    return load_json(SCRIPT_DIR / "expected_actions.json")


def source_id(action: dict) -> str | None:
    return action.get("source_message_id") or action.get("source_id") or action.get("message_id")


def action_by_source() -> dict[str, dict]:
    return {source_id(action): action for action in output().get("actions", []) if source_id(action)}


def non_action_ids() -> set[str]:
    ids: set[str] = set()
    for item in output().get("non_actions", []):
        sid = item.get("source_message_id") or item.get("source_id") or item.get("message_id")
        if sid:
            ids.add(sid)
    return ids


def text_blob(value) -> str:
    return json.dumps(value, ensure_ascii=False).lower()


class TestOutcome:
    def test_public_actions_exist(self):
        data = output()
        assert isinstance(data.get("actions"), list), "actions must be a list"
        assert len(data["actions"]) >= config()["public_min_actions"], f"expected at least {config()['public_min_actions']} actions"

    def test_public_actions_have_structure(self):
        for action in output().get("actions", []):
            assert action.get("source_message_id"), f"action missing source_message_id: {action}"
            assert action.get("assignee"), f"action missing assignee: {action}"
            assert action.get("description"), f"action missing description: {action}"

    def test_expected_action_recall(self):
        cfg = config()
        found = set(action_by_source())
        expected = set(expected_actions())
        missing = expected - found
        assert len(missing) <= cfg["allowed_missing_actions"], f"missing expected actions: {sorted(missing)}"

    def test_false_positive_control(self):
        cfg = config()
        action_ids = set(action_by_source())
        known_non_actions = set(cfg["non_action_source_ids"])
        false_positives = sorted(action_ids & known_non_actions)
        assert len(false_positives) <= cfg["max_false_positives"], f"non-actions marked as actions: {false_positives}"

    def test_expected_assignees_and_descriptions(self):
        actions = action_by_source()
        for source, expected in expected_actions().items():
            if source not in actions:
                continue
            action = actions[source]
            assignee = str(action.get("assignee", "")).lower()
            if expected["assignee"].lower() == "unspecified":
                assert assignee in {
                    "unspecified",
                    "team",
                    "product",
                    "product team",
                    "design",
                    "design team",
                }, f"{source} wrong assignee: {assignee}"
            else:
                assert expected["assignee"].lower() in assignee, f"{source} wrong assignee: {assignee}"
            blob = text_blob(action.get("description", ""))
            for term in expected.get("description_terms", []):
                assert term.lower() in blob, f"{source} description missing term {term!r}: {blob}"

    def test_implicit_and_question_action_types(self):
        actions = action_by_source()
        for source, expected in expected_actions().items():
            if source not in actions:
                continue
            action = actions[source]
            action_type = str(action.get("action_type", "")).lower()
            expected_type = expected.get("action_type", "").lower()
            assert expected_type in action_type, f"{source} expected action_type {expected_type!r}, got {action_type!r}"
            if expected.get("action_type") == "implicit":
                assert action.get("implicit") is True or "implicit" in action_type, f"{source} should be marked implicit"
                assert float(action.get("confidence", 0)) >= 0.6, f"{source} implicit action needs calibrated confidence"
            if expected.get("action_type") == "question_action":
                assert "question" in action_type or "request" in action_type, f"{source} should be treated as actionable question"

    def test_required_non_actions_are_classified(self):
        cfg = config()
        action_ids = set(action_by_source())
        non_ids = non_action_ids()
        for source in cfg["required_non_action_ids"]:
            assert source not in action_ids, f"{source} is rhetorical/chatter and must not be an action"
            assert source in non_ids, f"{source} should appear in non_actions with a reason"

    def test_required_non_action_reason_quality(self):
        reasons = {
            item.get("source_message_id") or item.get("source_id") or item.get("message_id"): str(item.get("reason", "")).lower()
            for item in output().get("non_actions", [])
        }
        for source in config()["required_non_action_ids"]:
            reason = reasons.get(source, "")
            assert any(token in reason for token in ["rhetorical", "chatter", "discussion", "social", "complaint", "non-action"]), f"{source} needs a specific non-action reason"

    def test_exact_counts_when_required(self):
        cfg = config()
        if cfg.get("exact_action_count"):
            assert len(output().get("actions", [])) == len(expected_actions()), "action count should match expected exactly"
        if cfg.get("exact_non_action_count"):
            assert len(output().get("non_actions", [])) == len(cfg["non_action_source_ids"]), "non-action count should match expected exactly"

    def test_implicit_recall_floor_when_required(self):
        floor = config().get("min_implicit_actions", 0)
        if not floor:
            return
        count = sum(1 for action in output().get("actions", []) if action.get("implicit") is True or "implicit" in str(action.get("action_type", "")).lower())
        assert count >= floor, f"expected at least {floor} implicit actions, got {count}"

    def test_expected_status_values(self):
        actions = action_by_source()
        for source, expected in expected_actions().items():
            if source not in actions:
                continue
            expected_status = expected.get("status", "open")
            assert actions[source].get("status") == expected_status, f"{source} wrong status"

    def test_gap_case_reason_quality(self):
        actions = action_by_source()
        for source, expected in expected_actions().items():
            if source not in actions:
                continue
            expected_type = expected.get("action_type")
            if expected_type not in {"implicit", "question_action"}:
                continue
            reason = str(actions[source].get("reason", "")).lower()
            assert any(token in reason for token in ["implicit", "delegation", "request", "actionable"]), f"{source} needs a gap-specific reason"

    def test_status_summary_and_followups(self):
        cfg = config()
        data = output()
        summary = data.get("status_summary", {})
        for key in cfg.get("required_status_keys", []):
            assert key in summary, f"missing status_summary key {key}"
        if cfg.get("min_follow_up_needed", 0):
            followups = data.get("summary", {}).get("follow_up_needed", [])
            assert len(followups) >= cfg["min_follow_up_needed"], "expected follow_up_needed entries in summary"

    def test_summary_contains_key_decisions(self):
        cfg = config()
        blob = text_blob(output().get("summary", {}))
        for keyword in cfg.get("summary_keywords", []):
            assert keyword.lower() in blob, f"summary missing keyword {keyword!r}"
