from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASKS_ROOT = REPO_ROOT / "benchmark" / "tasks"
INBOX_TRIAGE_TASKS = (
    "sort-20-explicit-priority",
    "implicit-urgency-30-emails",
    "sender-hierarchy-weight",
    "triage-for-meeting-prep",
    "anger-not-urgent-trap",
    "triage-then-draft-p0-replies",
)


def _e6_task_roots() -> list[Path]:
    roots: list[Path] = []
    for spec_path in TASKS_ROOT.glob("*/task-spec.yaml"):
        task_id = next(
            (
                line.split(":", 1)[1].strip()
                for line in spec_path.read_text(encoding="utf-8").splitlines()
                if line.startswith("task_id:")
            ),
            "",
        )
        if task_id.startswith("E6-"):
            roots.append(spec_path.parent)
    return sorted(roots)


def test_e6_process_verifiers_do_not_require_hidden_source_markers() -> None:
    task_roots = _e6_task_roots()
    assert len(task_roots) == 30

    marker_test_fragments = (
        "process_markers",
        "expected process marker",
        "expected marker",
        "capability_markers_for_advanced_cases",
        "policy_contains_required_capability_markers",
    )
    offenders: dict[str, list[str]] = {}
    for task_root in task_roots:
        process_text = (task_root / "tests" / "test_process.py").read_text(
            encoding="utf-8"
        )
        matches = [
            fragment for fragment in marker_test_fragments if fragment in process_text
        ]
        if matches:
            offenders[task_root.name] = matches

    assert not offenders, (
        "E6 process verifiers must exercise observable behavior instead of requiring "
        f"unpublished source words: {offenders}"
    )


def test_e6_ground_truth_does_not_publish_unused_source_marker_contracts() -> None:
    offenders: list[str] = []
    for task_root in _e6_task_roots():
        ground_truth_path = task_root / "tests" / "ground_truth.json"
        if not ground_truth_path.exists():
            continue
        payload = json.loads(ground_truth_path.read_text(encoding="utf-8"))
        if "process_markers" in payload:
            offenders.append(task_root.name)

    assert not offenders, (
        "retired source-marker fields should not remain in ground truth: "
        f"{offenders}"
    )


def test_e6_process_verifiers_retain_nonlexical_checks() -> None:
    too_small: dict[str, int] = {}
    for task_root in _e6_task_roots():
        process_text = (task_root / "tests" / "test_process.py").read_text(
            encoding="utf-8"
        )
        test_count = process_text.count("def test_")
        if test_count < 3:
            too_small[task_root.name] = test_count

    assert not too_small, (
        "removing lexical marker checks must not empty the process verifier: "
        f"{too_small}"
    )


def test_inbox_triage_family_publishes_one_consistent_priority_policy() -> None:
    required_policy = (
        "hard same-day/overnight",
        "including an explicit EOD deadline",
        "should be handled today but is not an active incident or hard same-day",
        "A clock or senior sender alone does not make a message P0",
        "independently from priority",
        "low-impact administrative, social",
    )
    missing: dict[str, list[str]] = {}
    for task_slug in INBOX_TRIAGE_TASKS:
        instruction = (TASKS_ROOT / task_slug / "instruction.md").read_text(
            encoding="utf-8"
        )
        normalized = " ".join(instruction.split())
        absent = [phrase for phrase in required_policy if phrase not in normalized]
        if absent:
            missing[task_slug] = absent

    assert not missing, (
        "all six inbox-triage tasks must expose the same P0-P3 policy so a model "
        f"does not have to infer hidden EOD semantics from verifier feedback: {missing}"
    )


def test_inbox_triage_rationales_do_not_require_hidden_keywords() -> None:
    offenders: dict[str, list[str]] = {}
    forbidden_contracts = ("reason_keywords", "reason_evidence_any")
    forbidden_checks = (
        "missing evidence words",
        "missing semantic evidence groups",
    )
    for task_slug in INBOX_TRIAGE_TASKS:
        task_root = TASKS_ROOT / task_slug
        ground_truth = json.loads(
            (task_root / "tests" / "ground_truth.json").read_text(encoding="utf-8")
        )
        outcome_text = (task_root / "tests" / "test_outcome.py").read_text(
            encoding="utf-8"
        )
        matches = [
            contract for contract in forbidden_contracts if contract in ground_truth
        ]
        matches.extend(
            check for check in forbidden_checks if check in outcome_text
        )
        if matches:
            offenders[task_slug] = matches

    assert not offenders, (
        "rationale quality may require a nontrivial explanation, but must not "
        f"force hidden wording that can reject a correct decision: {offenders}"
    )


def test_inbox_triage_hard_same_day_labels_match_published_policy() -> None:
    hard_blockers = {
        "sort-20-explicit-priority": {
            "email_003": "explicit EOD signature blocker",
        },
        "implicit-urgency-30-emails": {
            "email_011": "explicit EOD decision",
            "email_020": "same-day payment-hold blocker",
        },
        "sender-hierarchy-weight": {
            "manager_eod": "explicit EOD deadline",
        },
        "anger-not-urgent-trap": {
            "trap_client": "same-day signature blocker",
        },
        "triage-then-draft-p0-replies": {
            "renewal_escalation": "same-day signature blocker",
        },
    }
    wrong: dict[str, dict[str, str]] = {}
    for task_slug, expected in hard_blockers.items():
        ground_truth = json.loads(
            (TASKS_ROOT / task_slug / "tests" / "ground_truth.json").read_text(
                encoding="utf-8"
            )
        )
        for message_id, rationale in expected.items():
            actual = ground_truth["expected_priorities"].get(message_id)
            if actual != "P0":
                wrong.setdefault(task_slug, {})[message_id] = (
                    f"{actual!r}; {rationale}"
                )

    assert not wrong, (
        "the published policy assigns explicit EOD and same-day business "
        f"blockers to P0, so ground-truth labels must agree: {wrong}"
    )


def test_inbox_triage_near_term_client_fixture_is_after_today() -> None:
    task_root = TASKS_ROOT / "implicit-urgency-30-emails"
    calendar = json.loads(
        (task_root / "environment" / "calendar" / "today.json").read_text(
            encoding="utf-8"
        )
    )
    mailbox = json.loads(
        (task_root / "environment" / "mail" / "messages.json").read_text(
            encoding="utf-8"
        )
    )
    ground_truth = json.loads(
        (task_root / "tests" / "ground_truth.json").read_text(encoding="utf-8")
    )
    today = date.fromisoformat(calendar["today"])
    today_name = today.strftime("%A").lower()
    tomorrow_name = (today + timedelta(days=1)).strftime("%A").lower()
    message = next(item for item in mailbox["messages"] if item["id"] == "email_007")
    body = message["body"].lower()

    assert ground_truth["expected_priorities"]["email_007"] == "P1"
    assert tomorrow_name in body
    assert today_name not in body, (
        "a P1 near-term client fixture must not describe an already-arrived "
        "same-day customer blocker, which the published policy assigns to P0"
    )


def test_meeting_prep_labels_follow_the_published_routine_deadline_boundary() -> None:
    task_root = TASKS_ROOT / "triage-for-meeting-prep"
    ground_truth = json.loads(
        (task_root / "tests" / "ground_truth.json").read_text(encoding="utf-8")
    )
    expected_priorities = ground_truth["expected_priorities"]

    assert expected_priorities["meet_005"] == "P0"
    assert {
        message_id: expected_priorities[message_id]
        for message_id in ("meet_001", "meet_002", "meet_004", "meet_008")
    } == {
        "meet_001": "P1",
        "meet_002": "P1",
        "meet_004": "P1",
        "meet_008": "P1",
    }
    assert expected_priorities["meet_007"] == "P2"
    assert "meet_007" in ground_truth["expected_response_ids"]
