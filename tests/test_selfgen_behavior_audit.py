from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "ap" / "build_selfgen_behavior_audit.py"
SPEC = importlib.util.spec_from_file_location("build_selfgen_behavior_audit", SCRIPT)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def learning(model: str, task_id: str, *, selected: bool = True) -> dict:
    tier = int(task_id[-1])
    return {
        "model": model,
        "condition": "self_generated",
        "selected_run": selected,
        "task_id": task_id,
        "family_id": task_id.rsplit("-T", 1)[0],
        "tier": tier,
        "learning_attempts": 2,
        "initial_verifier_passed": False,
        "terminal_verifier_passed": True,
        "repaired_to_pass": True,
        "all_attempts_same_session_verified": True,
        "reflection_status": "completed",
        "failed_tests": [],
    }


def evaluation(
    model: str, task_id: str, *, passed: bool, selected: bool = True
) -> dict:
    family = task_id.rsplit("-T", 1)[0]
    return {
        "model": model,
        "condition": "self_generated",
        "selected_run": selected,
        "task_id": task_id,
        "family_id": family,
        "tier": int(task_id[-1]),
        "strict_pass": passed,
        "outcome_pass": passed,
        "process_pass": passed,
        "retrieved_skill_ids": [f"{family}.primary"],
        "skills_actually_used": [f"{family}.primary"],
        "failed_tests": [],
    }


def skill(model: str, family: str, *, selected: bool = True) -> dict:
    return {
        "model": model,
        "condition": "self_generated",
        "selected_run": selected,
        "family_id": family,
        "skill_id": f"{family}.primary",
        "skill_slug": "primary",
        "current_version": 2,
        "version_summaries": [
            {"version": 1, "summary": "initial"},
            {"version": 2, "summary": "revised"},
        ],
        "generated_chars": 100,
        "generated_text": "General runtime behavior.",
    }


def test_build_audit_filters_stale_runs_and_pairs_tasks() -> None:
    evidence = {"learning_tasks": [], "skills": [], "tasks": []}
    for model in ("left", "right"):
        for tier in range(1, 4):
            task_id = f"E1-LS1-T{tier}"
            evidence["learning_tasks"].append(learning(model, task_id))
            evidence["learning_tasks"].append(
                learning(model, task_id, selected=False)
            )
        evidence["skills"].append(skill(model, "E1-LS1"))
        evidence["skills"].append(skill(model, "E1-LS1", selected=False))
    for tier in range(4, 7):
        task_id = f"E1-LS1-T{tier}"
        evidence["tasks"].append(
            evaluation("left", task_id, passed=tier != 6)
        )
        evidence["tasks"].append(
            evaluation("right", task_id, passed=tier == 4)
        )
        evidence["tasks"].append(
            evaluation("left", task_id, passed=False, selected=False)
        )

    audit = MODULE.build_audit(evidence, "left", "right", None)

    assert audit["paired_summary"]["matched_tasks"] == 3
    assert audit["paired_summary"]["outcome"] == {
        "both_fail": 1,
        "both_pass": 1,
        "left_only": 1,
    }
    assert audit["model_summaries"]["left"]["learning_tasks"] == 3
    assert audit["model_summaries"]["left"]["active_skills"] == 1
    assert audit["model_summaries"]["left"]["evaluation_same_family_skill_used"] == 3
    family = audit["families"][0]["models"]["left"]
    assert family["learning_attempts"] == 6
    assert family["terminal_learning_passes"] == 3
    assert family["active_skill_count"] == 1
    assert family["same_family_skill_reads"] == 3
