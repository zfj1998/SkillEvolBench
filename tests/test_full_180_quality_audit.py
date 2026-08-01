from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "experiments/full_180_quality_audit/build_audit.py"
SPEC = importlib.util.spec_from_file_location("build_full_180_quality_audit", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
AUDIT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(AUDIT)

REPORT_SCRIPT = (
    ROOT / "experiments" / "full_180_quality_audit" / "build_report.py"
)
REPORT_SPEC = importlib.util.spec_from_file_location(
    "build_full_180_quality_report", REPORT_SCRIPT
)
assert REPORT_SPEC is not None and REPORT_SPEC.loader is not None
REPORT = importlib.util.module_from_spec(REPORT_SPEC)
REPORT_SPEC.loader.exec_module(REPORT)

FINALIZER_SCRIPT = (
    ROOT / "experiments" / "full_180_quality_audit" / "finalize_when_ready.py"
)
FINALIZER_SPEC = importlib.util.spec_from_file_location(
    "finalize_full_180_quality_audit", FINALIZER_SCRIPT
)
assert FINALIZER_SPEC is not None and FINALIZER_SPEC.loader is not None
FINALIZER = importlib.util.module_from_spec(FINALIZER_SPEC)
FINALIZER_SPEC.loader.exec_module(FINALIZER)


def test_finalizer_guardian_writes_one_valid_json_object() -> None:
    script = (
        ROOT
        / "experiments/full_180_quality_audit/run_finalizer_guardian.sh"
    ).read_text(encoding="utf-8")

    assert "printf '{{\"updated_at_utc\"" not in script
    assert "printf '{\"updated_at_utc\"" in script


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value) + "\n", encoding="utf-8")


def test_finalizer_requires_all_five_groups_and_30_safe_exports(
    tmp_path: Path,
) -> None:
    audit_root = tmp_path / "audit"
    finalizer = FINALIZER.Finalizer(
        SimpleNamespace(repo_root=ROOT, audit_root=audit_root, poll_sec=10)
    )

    ready, reason = finalizer.readiness()

    assert ready is None
    assert reason == "waiting for shuffled/reference groups to be submitted"

    group_ids = [f"group-{index}" for index in range(5)]
    reference_group_id = group_ids[-1]
    _write_json(
        audit_root / "missing-control-watcher/state.json",
        {
            "shuffled_group_id": group_ids[-2],
            "reference_group_id": reference_group_id,
        },
    )
    _write_json(
        audit_root / "watcher/manifest.json",
        {
            "groups": [{"group_id": group_id} for group_id in group_ids],
        },
    )
    jobs = []
    for group_index, group_id in enumerate(group_ids):
        for environment in range(1, 7):
            job_id = f"job-{group_index}-E{environment}"
            jobs.append(
                {
                    "job_id": job_id,
                    "group_id": group_id,
                    "instance_id": f"E{environment}",
                    "status": "Succeeded",
                }
            )
            _write_json(
                audit_root / f"watcher/exports/{job_id}.json",
                {"completed": True, "unsafe": False},
            )
    _write_json(audit_root / "watcher/inventory.json", {"jobs": jobs})

    ready, reason = finalizer.readiness()

    assert reason is None
    assert ready is not None
    assert len(ready["jobs"]) == 30
    assert ready["group_ids"] == sorted(group_ids)

    unsafe_job_id = jobs[0]["job_id"]
    _write_json(
        audit_root / f"watcher/exports/{unsafe_job_id}.json",
        {"completed": True, "unsafe": True},
    )
    ready, reason = finalizer.readiness()
    assert ready is None
    assert reason == "waiting for 1 safe exports"


def test_finalizer_can_launch_repo_local_ap_collector(tmp_path: Path) -> None:
    finalizer = FINALIZER.Finalizer(
        SimpleNamespace(repo_root=ROOT, audit_root=tmp_path, poll_sec=10)
    )

    result = finalizer.run_command(
        [
            sys.executable,
            str(ROOT / "scripts/ap/build_t56_oracle_study.py"),
            "--help",
        ],
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "--raw-root" in result.stdout


def test_generated_skill_update_is_linked_to_later_new_input_use() -> None:
    payload = {
        "skills": [{
            "skill_id": "E1-LS1.example",
            "created_at_task": "E1-LS1-T2",
            "last_revised_at_task": "E1-LS1-T2",
            "current_version": 1,
            "generated_path": "library/example/SKILL.md",
        }],
        "evaluation": [{
            "task_id": "E1-LS1-T4",
            "skills_actually_used": ["E1-LS1.example"],
        }],
    }

    result = AUDIT.generated_skill_reuse(payload, "E1-LS1-T2")

    assert [row["skill_id"] for row in result["skill_updates"]] == [
        "E1-LS1.example"
    ]
    assert result["later_evaluation_uses"] == [{
        "task_id": "E1-LS1-T4",
        "skill_ids": ["E1-LS1.example"],
    }]


def test_current_no_skill_pass_is_only_a_single_run_low_demand_screen() -> None:
    result = AUDIT.check_need(
        5,
        [{"category": "history_supported"}],
        [],
        {"no_skill": {"outcome_pass": True}},
    )

    assert result["status"] == "v1_1_single_run_low_skill_demand"
    assert "majority" in result["claim_boundary"]


def test_unrelated_skill_evidence_never_uses_curated_all_as_a_substitute() -> None:
    result = AUDIT.check_unrelated(6)

    assert result["status"] == "missing_strict_shuffled_curated_control"
    assert "curated-all" in result["claim_boundary"]


def test_current_controls_distinguish_expert_rescue_from_wrong_skill() -> None:
    no_skill = {"outcome_pass": False, "no_skill_empty": True}
    exact = {"outcome_pass": True, "oracle_injection_exact": True}
    shuffled = {
        "outcome_pass": False,
        "shuffled_injection_valid": True,
        "shuffled_gold_skill_ids": ["E1-LS1.gold"],
        "shuffled_skill_ids": ["E2-LS1.unrelated"],
        "shuffled_source_environment_id": "E2",
    }

    expert = AUDIT.current_expert_check(no_skill, exact)
    unrelated = AUDIT.current_unrelated_check(exact, shuffled)

    assert expert["status"] == "single_run_expert_rescue"
    assert unrelated["status"] == "single_run_correct_skill_specific"


def test_screening_queue_prioritizes_defect_evidence_without_drop_verdict() -> None:
    checks = {
        "1_experience_generation_and_reuse": {
            "status": "generated_skill_used_on_new_input"
        },
        "2_historical_skill_demand": {
            "status": "single_run_low_skill_demand"
        },
        "3_correct_expert_skill_effect": {"status": "single_run_both_pass"},
        "4_unrelated_skill_negative_control": {
            "status": "single_run_wrong_skill_insensitive"
        },
        "5_task_and_verifier_validity": {
            "reference_strict_pass": False,
            "process_only_failure_conditions": ["self_generated"],
            "model_execution_gap_candidate": False,
            "process_shape_sensitivity": "high",
        },
    }

    result = AUDIT.screening_assessment(5, checks)

    assert result["priority"] == "high"
    assert "reference_solution_failed" in result["flags"]
    assert "process_only_false_negative_candidate" in result["flags"]
    assert "low_skill_demand_candidate" in result["flags"]
    assert "wrong_skill_insensitive_candidate" in result["flags"]
    assert "not a keep/drop verdict" in result["claim_boundary"]


def test_manual_semantic_false_negative_enters_high_priority_queue() -> None:
    checks = {
        "1_experience_generation_and_reuse": {
            "status": "generated_skill_used_on_new_input"
        },
        "2_historical_skill_demand": {
            "status": "single_run_historical_skill_demand_candidate"
        },
        "3_correct_expert_skill_effect": {"status": "single_run_both_fail"},
        "4_unrelated_skill_negative_control": {
            "status": "single_run_neither_skill_passes"
        },
        "5_task_and_verifier_validity": {
            "reference_strict_pass": True,
            "process_only_failure_conditions": [],
            "model_execution_gap_candidate": False,
            "process_shape_sensitivity": "low",
            "manual_semantic_status": "confirmed_process_false_negative",
        },
    }

    result = AUDIT.screening_assessment(5, checks)

    assert result["priority"] == "high"
    assert result["flags"] == ["process_only_false_negative_candidate"]


def test_current_experience_links_reflection_update_to_new_input_use() -> None:
    spec = {"task_id": "E1-LS1-T2", "family_id": "E1-LS1"}
    current = {
        "learning": {
            "E1-LS1-T2": {
                "same_session_verified": True,
                "all_attempts_same_session_verified": True,
                "learning_attempts": 2,
                "reflection_status": "completed",
                "reflection_patch": {"operation_type": "update"},
            }
        },
        "skills": [
            {
                "skill_id": "E1-LS1.skill",
                "family_id": "E1-LS1",
                "created_at_task": "E1-LS1-T1",
                "last_revised_at_task": "E1-LS1-T2",
                "current_version": 2,
                "version_summaries": [
                    {"version": 2, "created_at_task": "E1-LS1-T2"}
                ],
            }
        ],
        "evaluation": {
            ("E1-LS1-T4", "self_generated"): {
                "family_id": "E1-LS1",
                "skills_actually_used": ["E1-LS1.skill"],
                "outcome_pass": True,
            }
        },
    }

    result = AUDIT.current_experience_check(spec, current)

    assert result["status"] == "skill_update_applied_and_used_on_later_new_input"
    assert result["learning"]["learning_attempts"] == 2
    assert result["later_new_input_uses"] == [
        {
            "task_id": "E1-LS1-T4",
            "skill_ids": ["E1-LS1.skill"],
            "outcome_pass": True,
        }
    ]


def test_complete_current_validator_requires_exact_180_task_evidence() -> None:
    specs = AUDIT.load_specs(ROOT / "benchmark" / "tasks")
    learning_ids = {
        str(spec["task_id"])
        for spec in specs
        if int(spec["task_index"]) <= 3
    }
    transfer_ids = {
        str(spec["task_id"])
        for spec in specs
        if int(spec["task_index"]) >= 4
    }
    evaluation = {}
    for task_id in transfer_ids:
        evaluation[(task_id, "self_generated")] = {}
        evaluation[(task_id, "no_skill")] = {"no_skill_empty": True}
        evaluation[(task_id, "exact_curated")] = {
            "oracle_injection_exact": True
        }
        evaluation[(task_id, "shuffled_curated")] = {
            "shuffled_injection_valid": True
        }
    runs = []
    for condition in AUDIT.CURRENT_CONDITIONS:
        for environment in range(1, 7):
            run = {
                "condition": condition,
                "environment_id": f"E{environment}",
                "ap_status": "Succeeded",
                "lifecycle_parse_errors": [],
                "evaluation_task_start_count": 15,
                "evaluation_task_end_count": 15,
                "library_frozen_before_evaluation": True,
                "evaluation_library_hash_stable": True,
                "benchmark_revision": "revision",
                "evaluation_only_t4_t6": condition != "self_generated",
                "learning_record_count": 15 if condition == "self_generated" else 0,
                "learning_max_attempts": 3 if condition == "self_generated" else 1,
                "baseline": "no_skill" if condition == "no_skill" else "curated_static",
                "oracle_skill_view": condition == "exact_curated",
                "shuffled_skill_view": condition == "shuffled_curated",
            }
            runs.append(run)
    current = {
        "learning": {task_id: {} for task_id in learning_ids},
        "evaluation": evaluation,
        "runs": runs,
        "skills": [],
    }
    reference = {
        str(spec["task_id"]): {"strict_pass": True} for spec in specs
    }

    errors = AUDIT.current_coverage_errors(
        specs, current, reference, "revision"
    )
    assert errors == []

    reference[next(iter(reference))]["strict_pass"] = False
    errors = AUDIT.current_coverage_errors(
        specs, current, reference, "revision"
    )
    assert errors == []

    current["evaluation"].pop((next(iter(transfer_ids)), "shuffled_curated"))
    errors = AUDIT.current_coverage_errors(
        specs, current, reference, "revision"
    )
    assert "current shuffled_curated grid is not the exact 90 T4-T6 tasks" in errors


def test_interactive_report_keeps_all_180_rows_and_escapes_script_end() -> None:
    tasks = []
    for environment in range(1, 7):
        for family in range(1, 6):
            for tier in range(1, 7):
                task_id = f"E{environment}-LS{family}-T{tier}"
                tasks.append(
                    {
                        "task_id": task_id,
                        "task_slug": f"task-{task_id}",
                        "environment_id": f"E{environment}",
                        "family_id": f"E{environment}-LS{family}",
                        "tier": tier,
                        "role": "canonical",
                        "readiness": "ready",
                        "screening_priority": "high",
                        "screening_flags": ["reference_solution_failed"],
                        "instruction": "safe </script><script>alert(1)</script>",
                        "checks": {
                            key: {"status": "checked"} for key in REPORT.POINT_KEYS
                        },
                    }
                )
    payload = REPORT.report_payload(
        {
            "schema_version": "test",
            "benchmark_revision": "revision",
            "claim_boundary": "screen",
            "summary": {
                "task_count": 180,
                "ready_for_final_five_point_decision": 180,
            },
            "tasks": tasks,
        }
    )
    rendered = REPORT.render_html(payload)

    assert len(payload["tasks"]) == 180
    assert payload["heatmap"][-1] == {
        "environment_id": "E6",
        "tier": 6,
        "ready": 5,
        "total": 5,
    }
    assert "E6-LS5-T6" in rendered
    assert "</script><script>alert(1)" not in rendered
