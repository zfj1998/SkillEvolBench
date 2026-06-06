from __future__ import annotations
import json
import os
import subprocess
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"])
SCRIPT_DIR = Path(os.environ["SCRIPT_DIR"])
GT = json.loads((SCRIPT_DIR / "ground_truth.json").read_text(encoding="utf-8"))

def setup_module():
    subprocess.run([os.environ.get("PYTHON_BIN", "python3"), "scheduler.py"], cwd=PROJECT_ROOT, check=True)

def output():
    path = PROJECT_ROOT / "output" / "schedule.json"
    assert path.exists(), "output/schedule.json was not created"
    return json.loads(path.read_text(encoding="utf-8"))

class TestOutcome:
    def test_recommendation_or_meetings_exist(self):
        result = output()
        assert result.get("recommendations") or result.get("scheduled_meetings"), "no schedule output"

    def test_expected_first_slot_or_meeting_order(self):
        result = output()
        if GT.get("expected_ranked_slot_ids"):
            actual = [item.get("slot_id") for item in result.get("recommendations", [])]
            assert actual[: len(GT["expected_ranked_slot_ids"])] == GT["expected_ranked_slot_ids"], f"slot rank mismatch: {actual}"
        if GT.get("expected_meeting_ids"):
            actual = [item.get("meeting_id") for item in result.get("scheduled_meetings", [])]
            assert actual == GT["expected_meeting_ids"], f"meeting ids mismatch: {actual}"

    def test_required_slots_present(self):
        result = output()
        starts = {item.get("start_utc") for item in result.get("recommendations", [])}
        starts |= {item.get("start_utc") for item in result.get("scheduled_meetings", [])}
        for start in GT.get("required_start_utc", []):
            assert start in starts, f"required start time missing: {start}"

    def test_forbidden_slots_absent(self):
        result = output()
        starts = {item.get("start_utc") for item in result.get("recommendations", [])}
        starts |= {item.get("start_utc") for item in result.get("scheduled_meetings", [])}
        for start in GT.get("forbidden_start_utc", []):
            assert start not in starts, f"forbidden slot was recommended: {start}"

    def test_scores_and_reasons_present(self):
        result = output()
        items = result.get("recommendations", []) + result.get("scheduled_meetings", [])
        assert all("reasons" in item and item["reasons"] for item in items), "each schedule item needs reasons"
        if GT.get("requires_scores"):
            assert all("score" in item for item in items), "scores required for optimization tasks"

    def test_expected_scores_match_soft_constraints(self):
        expected_scores = GT.get("expected_scores", {})
        if not expected_scores:
            return
        items = result = output()
        by_id = {item.get("slot_id") or item.get("meeting_id"): item for item in result.get("recommendations", []) + result.get("scheduled_meetings", [])}
        wrong = {item_id: (by_id.get(item_id, {}).get("score"), score) for item_id, score in expected_scores.items() if by_id.get(item_id, {}).get("score") != score}
        assert not wrong, f"score mismatch: {wrong}"

    def test_soft_preference_counts_match(self):
        expected = GT.get("expected_soft_preferences_met", {})
        if not expected:
            return
        result = output()
        by_id = {item.get("slot_id") or item.get("meeting_id"): item for item in result.get("recommendations", []) + result.get("scheduled_meetings", [])}
        wrong = {item_id: (by_id.get(item_id, {}).get("soft_preferences_met"), count) for item_id, count in expected.items() if by_id.get(item_id, {}).get("soft_preferences_met") != count}
        assert not wrong, f"soft preference count mismatch: {wrong}"

    def test_reason_terms_explain_preferences(self):
        expected = GT.get("expected_reason_terms", {})
        if not expected:
            return
        result = output()
        by_id = {item.get("slot_id") or item.get("meeting_id"): item for item in result.get("recommendations", []) + result.get("scheduled_meetings", [])}
        for item_id, terms in expected.items():
            reason_text = " ".join(by_id.get(item_id, {}).get("reasons", [])).lower()
            missing = [term for term in terms if term.lower() not in reason_text]
            assert not missing, f"{item_id} reason missing {missing}: {reason_text}"

    def test_preference_breakdown_matches_participants(self):
        expected = GT.get("expected_preference_breakdown", {})
        if not expected:
            return
        result = output()
        by_id = {item.get("slot_id") or item.get("meeting_id"): item for item in result.get("recommendations", []) + result.get("scheduled_meetings", [])}
        for item_id, participant_map in expected.items():
            breakdown = by_id.get(item_id, {}).get("preference_breakdown", {})
            for participant, satisfied in participant_map.items():
                assert breakdown.get(participant) is satisfied, f"{item_id} preference for {participant}: {breakdown.get(participant)} != {satisfied}"

    def test_local_times_and_dst_offsets(self):
        result = output()
        items = result.get("recommendations", []) + result.get("scheduled_meetings", [])
        if not GT.get("expected_local_times"):
            return
        text = json.dumps(items, ensure_ascii=False)
        for token in GT["expected_local_times"]:
            assert token in text, f"expected local-time/DST token missing: {token}"

    def test_soft_preference_count(self):
        result = output()
        if "min_soft_preferences_met" not in GT:
            return
        met = sum(item.get("soft_preferences_met", 0) for item in result.get("scheduled_meetings", []))
        assert met >= GT["min_soft_preferences_met"], f"soft preferences met too low: {met}"
