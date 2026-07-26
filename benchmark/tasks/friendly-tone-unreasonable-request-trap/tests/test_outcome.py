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
    subprocess.run([os.environ.get("PYTHON_BIN", "python3"), "reply_pipeline.py"], cwd=PROJECT_ROOT, check=True)

def load_output():
    path = PROJECT_ROOT / "output" / "replies.json"
    assert path.exists(), "output/replies.json was not created"
    return json.loads(path.read_text(encoding="utf-8"))

class TestOutcome:
    def test_expected_reply_ids(self):
        output = load_output()
        actual = {reply["email_id"] for reply in output.get("replies", [])}
        expected = set(GT.get("expected_reply_ids", []))
        assert actual == expected, f"reply ids mismatch: actual={sorted(actual)} expected={sorted(expected)}"

    def test_acknowledge_and_ignore_ids(self):
        output = load_output()
        actual_ack = {reply["email_id"] for reply in output.get("acknowledgements", [])}
        actual_ignore = {item["email_id"] for item in output.get("ignored", [])}
        assert actual_ack == set(GT.get("expected_ack_ids", [])), f"ack ids mismatch: {sorted(actual_ack)}"
        assert actual_ignore == set(GT.get("expected_ignore_ids", [])), f"ignore ids mismatch: {sorted(actual_ignore)}"

    def test_required_content_terms(self):
        output = load_output()
        replies = {reply["email_id"]: reply for reply in output.get("replies", [])}
        for mid, groups in GT.get("required_terms", {}).items():
            body = replies.get(mid, {}).get("body", "").lower()
            assert body, f"missing reply body for {mid}"
            for group in groups:
                assert any(term.lower() in body for term in group), f"reply {mid} missing one of {group}: {body}"

    def test_required_term_group_coverage_ratio(self):
        output = load_output()
        replies = {reply["email_id"]: reply for reply in output.get("replies", [])}
        for mid, expected_count in GT.get("min_required_groups", {}).items():
            body = replies.get(mid, {}).get("body", "").lower()
            groups = GT.get("required_terms", {}).get(mid, [])
            matched = sum(1 for group in groups if any(term.lower() in body for term in group))
            assert matched >= expected_count, f"reply {mid} matched {matched}/{len(groups)} required content groups"

    def test_specificity_terms_present(self):
        output = load_output()
        replies = {reply["email_id"]: reply for reply in output.get("replies", [])}
        for mid, terms in GT.get("specificity_terms", {}).items():
            body = replies.get(mid, {}).get("body", "").lower()
            missing = [term for term in terms if term.lower() not in body]
            assert not missing, f"reply {mid} missing specificity terms {missing}: {body}"

    def test_forbidden_content_absent(self):
        output = load_output()
        text = json.dumps(output, ensure_ascii=False).lower()
        for phrase in GT.get("forbidden_phrases", []):
            assert phrase.lower() not in text, f"forbidden phrase present: {phrase}"

    def test_expected_cc_is_preserved(self):
        output = load_output()
        replies = {reply["email_id"]: reply for reply in output.get("replies", [])}
        for mid, expected_cc in GT.get("expected_cc", {}).items():
            actual_cc = set(replies.get(mid, {}).get("cc", []))
            assert set(expected_cc).issubset(actual_cc), f"reply {mid} missing cc: {set(expected_cc) - actual_cc}"

    def test_rationales_explain_context_use(self):
        output = load_output()
        replies = {reply["email_id"]: reply for reply in output.get("replies", [])}
        semantic_alternatives = {
            "scope": ("scope", "staged", "phased", "safe_friday_scope"),
            "timeline": ("timeline", "friday", "three months", "schedule"),
        }
        for mid, keywords in GT.get("rationale_keywords", {}).items():
            rationale = replies.get(mid, {}).get("rationale", "").lower()
            for keyword in keywords:
                alternatives = semantic_alternatives.get(
                    keyword.lower(), (keyword.lower(),)
                )
                assert any(term in rationale for term in alternatives), (
                    f"rationale for {mid} missing semantic evidence for "
                    f"{keyword!r}: {rationale}"
                )
