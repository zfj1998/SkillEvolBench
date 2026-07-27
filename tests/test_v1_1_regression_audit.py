from __future__ import annotations

import pytest

from scripts.ap.build_v1_1_regression_audit import build_audit


def task(job_id: str, family: int, tier: int, passed: bool) -> dict[str, object]:
    return {
        "job_id": job_id,
        "environment_id": "E6",
        "selected_run": True,
        "task_id": f"E6-LS{family}-T{tier}",
        "family_id": f"E6-LS{family}",
        "tier": tier,
        "strict_pass": passed,
        "outcome_pass": passed,
        "process_pass": passed,
        "skills_actually_used": ["E6-LS1.example"] if job_id == "selfgen" else [],
        "retrieved_skill_ids": ["E6-LS1.example"] if job_id == "selfgen" else [],
        "failed_tests": [] if passed else [{"name": "test_failure"}],
    }


def evidence() -> dict[str, object]:
    tasks = []
    learning = []
    for family in range(1, 6):
        for tier in range(4, 7):
            tasks.append(task("selfgen", family, tier, tier != 6))
            tasks.append(task("no-skill", family, tier, tier == 4))
        for tier in range(1, 4):
            learning.append(
                {
                    "job_id": "selfgen",
                    "environment_id": "E6",
                    "selected_run": True,
                    "task_id": f"E6-LS{family}-T{tier}",
                    "learning_attempts": 2,
                    "initial_verifier_passed": False,
                    "terminal_verifier_passed": True,
                    "repaired_to_pass": True,
                    "all_attempts_same_session_verified": True,
                    "reflection_status": "completed",
                }
            )
    return {
        "runs": [
            {
                "job_id": "selfgen",
                "environment_id": "E6",
                "selected_run": True,
                "condition": "self_generated",
                "baseline": "selfgen_in_session_always",
                "model_name": "anthropic/claude-opus-4-8",
                "benchmark_revision": "revision-1",
                "ap_attempt": 0,
                "runtime_attempt": 0,
                "ap_status": "Succeeded",
                "learning_max_attempts": 3,
                "evaluation_only_t4_t6": False,
                "library_freeze_event_count": 1,
                "library_frozen_before_evaluation": True,
                "evaluation_library_hashes": ["abc123"],
                "evaluation_library_hash_stable": True,
                "evaluation_task_start_count": 15,
                "evaluation_task_end_count": 15,
            },
            {
                "job_id": "no-skill",
                "environment_id": "E6",
                "selected_run": True,
                "condition": "no_skill",
                "baseline": "no_skill",
                "model_name": "anthropic/claude-opus-4-8",
                "benchmark_revision": "revision-1",
                "ap_attempt": 0,
                "runtime_attempt": 0,
                "ap_status": "Succeeded",
                "evaluation_only_t4_t6": True,
            },
        ],
        "tasks": tasks,
        "learning_tasks": learning,
        "skills": [
            {
                "job_id": "selfgen",
                "environment_id": "E6",
                "selected_run": True,
                "skill_id": "E6-LS1.example",
                "family_id": "E6-LS1",
                "generated_text": "# Example skill",
                "version_summaries": [{"version": 1}],
            }
        ],
    }


def test_build_audit_pairs_exact_jobs_and_summarizes_rescue() -> None:
    result = build_audit(
        evidence(),
        selfgen_job_id="selfgen",
        no_skill_job_id="no-skill",
        environment_id="E6",
        split="v1.1@1",
    )
    assert result["learning"]["tasks"] == 15
    assert result["learning"]["terminal_pass"] == 15
    assert len(result["learning"]["task_records"]) == 15
    assert result["learning"]["skills"][0]["generated_text"] == "# Example skill"
    assert result["self_generated"]["strict_pass"] == 10
    assert result["no_skill"]["strict_pass"] == 5
    assert result["paired_summary"]["strict"] == {
        "both_fail": 5,
        "both_pass": 5,
        "skill_rescue": 5,
    }
    assert len(result["paired_tasks"]) == 15
    assert result["protocol"]["same_model_name"] == "anthropic/claude-opus-4-8"
    assert result["protocol"]["same_benchmark_revision"] == "revision-1"
    assert result["protocol"]["self_generated_library_frozen_before_evaluation"]


def test_build_audit_rejects_incomplete_condition() -> None:
    value = evidence()
    value["tasks"] = [
        row
        for row in value["tasks"]
        if not (row["job_id"] == "no-skill" and row["task_id"] == "E6-LS5-T6")
    ]
    with pytest.raises(ValueError, match="no-skill job has 14/15"):
        build_audit(
            value,
            selfgen_job_id="selfgen",
            no_skill_job_id="no-skill",
            environment_id="E6",
            split="v1.1@1",
        )
