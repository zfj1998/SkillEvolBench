#!/usr/bin/env python3
"""Join static and dynamic evidence into one row per SkillEvolBench task.

The output is deliberately conservative: legacy v1 runs are useful diagnostic
evidence but never fill a missing v1.1 control cell.  In particular, the lack
of a strict shuffled-skill condition remains visible on every T4--T6 row.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import os
import subprocess
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml


CURRENT_CONDITIONS = (
    "self_generated",
    "no_skill",
    "exact_curated",
    "shuffled_curated",
)
CONDITION_ALIASES = {"exact_oracle": "exact_curated"}


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    try:
        temporary.write_text(text, encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def revision(root: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=root,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else "unknown"


def load_specs(tasks_root: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for path in sorted(tasks_root.glob("*/task-spec.yaml")):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(spec, dict):
            raise ValueError(f"invalid task spec: {path}")
        instruction_path = path.parent / "instruction.md"
        instruction = instruction_path.read_text(encoding="utf-8")
        rows.append(
            {
                **spec,
                "task_spec_path": str(path.resolve()),
                "instruction_path": str(instruction_path.resolve()),
                "instruction_sha256": hashlib.sha256(instruction.encode()).hexdigest(),
                "instruction": instruction,
            }
        )
    ids = [str(row.get("task_id")) for row in rows]
    if len(rows) != 180 or len(set(ids)) != 180:
        raise ValueError(
            f"expected 180 unique task specs, got rows={len(rows)} unique={len(set(ids))}"
        )
    return sorted(
        rows,
        key=lambda row: (
            str(row["environment_id"]),
            str(row["family_id"]),
            int(row["task_index"]),
        ),
    )


def behavior_index(behavior: dict[str, Any]) -> dict[tuple[str, str], dict[str, Any]]:
    return {
        (str(family["family_id"]), str(model)): payload
        for family in behavior.get("families", [])
        for model, payload in family.get("models", {}).items()
    }


def generated_skill_reuse(payload: dict[str, Any], task_id: str) -> dict[str, Any]:
    created = [
        skill
        for skill in payload.get("skills", [])
        if skill.get("created_at_task") == task_id
        or skill.get("last_revised_at_task") == task_id
    ]
    ids = {str(skill.get("skill_id")) for skill in created}
    uses = []
    for task in payload.get("evaluation", []):
        used = set(map(str, task.get("skills_actually_used") or []))
        overlap = sorted(ids & used)
        if overlap:
            uses.append({"task_id": task.get("task_id"), "skill_ids": overlap})
    return {
        "skill_updates": [
            {
                "skill_id": skill.get("skill_id"),
                "created_at_task": skill.get("created_at_task"),
                "last_revised_at_task": skill.get("last_revised_at_task"),
                "current_version": skill.get("current_version"),
                "verifier_marker_hits": skill.get("verifier_marker_hits"),
                "generated_path": skill.get("generated_path"),
            }
            for skill in created
        ],
        "later_evaluation_uses": uses,
    }


def check_experience(
    spec: dict[str, Any],
    behavior: dict[tuple[str, str], dict[str, Any]],
) -> dict[str, Any]:
    family_id = str(spec["family_id"])
    task_id = str(spec["task_id"])
    tier = int(spec["task_index"])
    models: dict[str, Any] = {}
    for (family, model), payload in sorted(behavior.items()):
        if family != family_id:
            continue
        if tier <= 3:
            learning = next(
                (
                    row
                    for row in payload.get("learning", [])
                    if row.get("task_id") == task_id
                ),
                None,
            )
            models[model] = {
                "learning": learning,
                **generated_skill_reuse(payload, task_id),
            }
        else:
            evaluation = next(
                (
                    row
                    for row in payload.get("evaluation", [])
                    if row.get("task_id") == task_id
                ),
                None,
            )
            models[model] = {
                "family_active_skill_count": payload.get("active_skill_count"),
                "evaluation": evaluation,
            }
    if tier <= 3:
        reusable = sum(
            bool(row.get("later_evaluation_uses")) for row in models.values()
        )
        updated = sum(bool(row.get("skill_updates")) for row in models.values())
        status = (
            "legacy_candidate_reused_on_new_input"
            if reusable
            else "legacy_candidate_generated_without_observed_reuse"
            if updated
            else "legacy_no_valid_skill_update"
        )
    else:
        reads = sum(
            bool((row.get("evaluation") or {}).get("same_family_skill_used"))
            for row in models.values()
        )
        status = (
            "legacy_same_family_skill_read"
            if reads
            else "legacy_no_same_family_skill_read"
        )
    return {
        "status": status,
        "evidence_revision": "legacy_v1_runtime",
        "claim_boundary": (
            "Generation and later reads show reusable state flow, not causal usefulness. "
            "The task/verifier assets changed in v1.1."
        ),
        "models": models,
    }


def measurement_index(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report.get("measurement_validity", {}).get("records", []):
        grouped[str(row.get("task_id"))].append(row)
    return grouped


def comparison_index(report: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in report.get("comparisons", []):
        grouped[str(row.get("task_id"))].append(row)
    return grouped


def compact_condition(value: Any) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        return None
    return {
        "strict": value.get("strict"),
        "outcome": value.get("outcome"),
        "process": value.get("process"),
        "score": value.get("score"),
        "job_id": value.get("job_id"),
    }


def legacy_condition_rows(comparisons: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "model": row.get("model"),
            "self_generated": compact_condition(row.get("conditions", {}).get("self_generated")),
            "no_skill": compact_condition(row.get("conditions", {}).get("no_skill")),
            "exact_curated": compact_condition(row.get("conditions", {}).get("exact_oracle")),
            "curated_all": compact_condition(row.get("conditions", {}).get("curated_all")),
        }
        for row in comparisons
    ]


def check_need(
    tier: int,
    measurements: list[dict[str, Any]],
    legacy_conditions: list[dict[str, Any]],
    current_pair: dict[str, Any] | None,
) -> dict[str, Any]:
    if tier <= 3:
        return {"status": "not_applicable_learning_task"}
    categories = sorted({str(row.get("category")) for row in measurements})
    legacy_no_skill = [
        row["no_skill"].get("outcome")
        for row in legacy_conditions
        if row.get("no_skill") is not None
    ]
    current_no_skill = (
        current_pair.get("no_skill", {}).get("outcome_pass")
        if current_pair
        else None
    )
    if current_no_skill is True:
        status = "v1_1_single_run_low_skill_demand"
    elif current_no_skill is False:
        status = "v1_1_single_run_skill_demand_candidate"
    elif categories and set(categories) <= {"on_task_only"}:
        status = "legacy_on_task_only_not_historical_transfer"
    elif legacy_no_skill and all(value is True for value in legacy_no_skill):
        status = "legacy_low_skill_demand_unconfirmed_v1_1"
    else:
        status = "insufficient_v1_1_no_skill_evidence"
    return {
        "status": status,
        "current_v1_1_no_skill_outcome": current_no_skill,
        "legacy_measurement_categories": categories,
        "legacy_no_skill_outcomes": legacy_no_skill,
        "claim_boundary": "One run is a screen; majority status needs repeated valid samples.",
    }


def check_expert(
    tier: int,
    legacy_conditions: list[dict[str, Any]],
) -> dict[str, Any]:
    if tier <= 3:
        return {"status": "not_applicable_learning_task"}
    deltas: list[dict[str, Any]] = []
    for row in legacy_conditions:
        no_skill = row.get("no_skill")
        exact = row.get("exact_curated")
        if no_skill is None or exact is None:
            continue
        before = no_skill.get("outcome")
        after = exact.get("outcome")
        label = (
            "rescue" if before is False and after is True
            else "harm" if before is True and after is False
            else "same_pass" if before is True and after is True
            else "same_fail" if before is False and after is False
            else "unknown"
        )
        deltas.append({"model": row.get("model"), "outcome_delta": label})
    return {
        "status": "missing_v1_1_exact_curated",
        "legacy_diagnostics": deltas,
        "claim_boundary": "Legacy deltas locate candidates but cannot score repaired v1.1 tasks.",
    }


def check_unrelated(tier: int) -> dict[str, Any]:
    if tier <= 3:
        return {"status": "not_applicable_learning_task"}
    return {
        "status": "missing_strict_shuffled_curated_control",
        "claim_boundary": (
            "Legacy curated-all contains the correct skill and is not an unrelated-skill control."
        ),
    }


def reference_index(reference: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("task_id")): row
        for row in reference.get("tasks", [])
        if row.get("task_id")
    }


def check_verifier(
    spec: dict[str, Any],
    static: dict[str, Any],
    reference: dict[str, Any] | None,
    repaired: bool,
) -> dict[str, Any]:
    tier = int(spec["task_index"])
    risk = static.get("process_shape_sensitivity")
    if reference and reference.get("strict_pass") is not True:
        status = "reference_solution_failed"
    elif reference:
        status = (
            "v1_1_repaired_reference_passed_needs_semantic_probe"
            if repaired
            else "v1_1_reference_passed_no_registered_contract_defect"
        )
    else:
        status = "no_dynamic_reference_audit_for_learning_task"
    if risk == "high":
        status += ":high_process_shape_review"
    return {
        "status": status,
        "reference_strict_pass": reference.get("strict_pass") if reference else None,
        "reference_trial_count": reference.get("trial_count") if reference else None,
        "known_v1_repair_applied": repaired,
        "process_shape_sensitivity": risk,
        "process_shape_reasons": static.get("process_shape_reasons") or [],
        "process_checks": static.get("process", {}).get("check_count"),
        "outcome_checks": static.get("outcome", {}).get("check_count"),
        "effective_process_weight_percent": static.get("effective_scoring", {}).get(
            "effective_process_weight_percent"
        ),
        "claim_boundary": (
            "Reference pass proves internal solvability only. High static risk is a review flag, "
            "not a defect finding."
        ),
    }


def load_current_pairs(regression: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(row.get("task_id")): row
        for row in regression.get("paired_tasks", [])
        if row.get("task_id")
    }


def current_evidence_index(
    evidence: dict[str, Any],
    expected_model: str,
) -> dict[str, Any]:
    def selected(row: dict[str, Any]) -> bool:
        return row.get("selected_run") is True and row.get("model") == expected_model

    runs = [
        row
        for row in evidence.get("runs", [])
        if isinstance(row, dict) and selected(row)
    ]
    evaluation_rows: dict[tuple[str, str], dict[str, Any]] = {}
    for row in evidence.get("tasks", []):
        if not isinstance(row, dict) or not selected(row):
            continue
        condition = CONDITION_ALIASES.get(
            str(row.get("condition")), str(row.get("condition"))
        )
        key = (str(row.get("task_id")), condition)
        if key in evaluation_rows:
            raise ValueError(f"duplicate selected current evidence row: {key!r}")
        evaluation_rows[key] = row

    learning_rows: dict[str, dict[str, Any]] = {}
    for row in evidence.get("learning_tasks", []):
        if (
            not isinstance(row, dict)
            or not selected(row)
            or row.get("condition") != "self_generated"
        ):
            continue
        task_id = str(row.get("task_id"))
        if task_id in learning_rows:
            raise ValueError(f"duplicate selected current learning row: {task_id}")
        learning_rows[task_id] = row

    skills = [
        row
        for row in evidence.get("skills", [])
        if isinstance(row, dict)
        and selected(row)
        and row.get("condition") == "self_generated"
    ]
    return {
        "runs": runs,
        "evaluation": evaluation_rows,
        "learning": learning_rows,
        "skills": skills,
    }


def compact_current_condition(row: dict[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    return {
        "strict_pass": row.get("strict_pass"),
        "outcome_pass": row.get("outcome_pass"),
        "process_pass": row.get("process_pass"),
        "normalized_score": row.get("normalized_score"),
        "classification": row.get("classification"),
        "failed_tests": row.get("failed_tests") or [],
        "skills_actually_used": row.get("skills_actually_used") or [],
        "retrieved_skill_ids": row.get("retrieved_skill_ids") or [],
        "job_id": row.get("job_id"),
        "run_id": row.get("run_id"),
        "record_path": row.get("record_path"),
        "local_trajectory_path": row.get("local_trajectory_path"),
    }


def current_experience_check(
    spec: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(spec["task_id"])
    learning = current["learning"].get(task_id)
    if learning is None:
        return {
            "status": "missing_current_learning_evidence",
            "evidence_revision": "v1.1_current_matrix",
        }

    updated_skills: list[dict[str, Any]] = []
    for skill in current["skills"]:
        versions = [
            version
            for version in skill.get("version_summaries") or []
            if isinstance(version, dict)
            and version.get("created_at_task") == task_id
        ]
        if (
            skill.get("created_at_task") == task_id
            or skill.get("last_revised_at_task") == task_id
            or versions
        ):
            updated_skills.append(
                {
                    "skill_id": skill.get("skill_id"),
                    "created_at_task": skill.get("created_at_task"),
                    "last_revised_at_task": skill.get("last_revised_at_task"),
                    "current_version": skill.get("current_version"),
                    "versions_from_task": versions,
                    "generated_path": skill.get("generated_path"),
                    "generated_sha256": skill.get("generated_sha256"),
                }
            )
    updated_ids = {
        str(skill["skill_id"])
        for skill in updated_skills
        if skill.get("skill_id")
    }
    later_uses: list[dict[str, Any]] = []
    for (later_task_id, condition), row in sorted(current["evaluation"].items()):
        if condition != "self_generated" or row.get("family_id") != spec["family_id"]:
            continue
        used = set(map(str, row.get("skills_actually_used") or []))
        overlap = sorted(updated_ids & used)
        if overlap:
            later_uses.append(
                {
                    "task_id": later_task_id,
                    "skill_ids": overlap,
                    "outcome_pass": row.get("outcome_pass"),
                }
            )

    protocol_ok = (
        learning.get("same_session_verified") is True
        and learning.get("all_attempts_same_session_verified") is True
        and isinstance(learning.get("learning_attempts"), int)
        and 1 <= int(learning["learning_attempts"]) <= 3
    )
    reflection_ok = (
        learning.get("reflection_status") == "completed"
        and isinstance(learning.get("reflection_patch"), dict)
    )
    if not protocol_ok:
        status = "same_session_or_attempt_protocol_failed"
    elif not reflection_ok:
        status = "reflection_or_patch_missing"
    elif updated_skills and later_uses:
        status = "skill_update_applied_and_used_on_later_new_input"
    elif updated_skills:
        status = "skill_update_applied_without_observed_later_use"
    else:
        status = "reflection_completed_without_applied_skill_update"
    return {
        "status": status,
        "evidence_revision": "v1.1_current_matrix",
        "protocol_ok": protocol_ok,
        "reflection_ok": reflection_ok,
        "learning": {
            key: learning.get(key)
            for key in (
                "strict_pass",
                "outcome_pass",
                "process_pass",
                "learning_attempts",
                "repair_attempts",
                "initial_verifier_passed",
                "terminal_verifier_passed",
                "repaired_to_pass",
                "same_session_verified",
                "all_attempts_same_session_verified",
                "reflection_status",
                "reflection_mode",
                "reflection_patch",
                "job_id",
                "run_id",
                "local_reflection_path",
            )
        },
        "skill_updates": updated_skills,
        "later_new_input_uses": later_uses,
        "claim_boundary": (
            "This proves same-session reflection, an applied library update, and later "
            "new-input visibility/use when present; causal usefulness is decided by the "
            "matched T4-T6 controls."
        ),
    }


def current_need_check(
    row: dict[str, Any] | None,
    legacy: dict[str, Any],
) -> dict[str, Any]:
    if row is None:
        return {"status": "missing_current_no_skill_evidence"}
    if row.get("no_skill_empty") is not True:
        return {
            "status": "invalid_no_skill_control_nonempty",
            "condition": compact_current_condition(row),
        }
    status = (
        "single_run_low_skill_demand"
        if row.get("outcome_pass") is True
        else "single_run_historical_skill_demand_candidate"
        if row.get("outcome_pass") is False
        else "invalid_no_skill_outcome"
    )
    return {
        "status": status,
        "condition": compact_current_condition(row),
        "legacy_measurement_categories": legacy.get(
            "legacy_measurement_categories", []
        ),
        "claim_boundary": (
            "One matched run screens demand. A stable task-level claim requires valid "
            "repeats for outcome-flip or otherwise critical rows."
        ),
    }


def current_expert_check(
    no_skill: dict[str, Any] | None,
    exact: dict[str, Any] | None,
) -> dict[str, Any]:
    if no_skill is None or exact is None:
        return {"status": "missing_current_exact_or_no_skill_evidence"}
    if exact.get("oracle_injection_exact") is not True:
        return {
            "status": "invalid_exact_skill_injection",
            "no_skill": compact_current_condition(no_skill),
            "exact_curated": compact_current_condition(exact),
            "injection_errors": exact.get("oracle_injection_errors") or [],
        }
    before = no_skill.get("outcome_pass")
    after = exact.get("outcome_pass")
    label = (
        "single_run_expert_rescue"
        if before is False and after is True
        else "single_run_expert_harm"
        if before is True and after is False
        else "single_run_both_pass"
        if before is True and after is True
        else "single_run_both_fail"
        if before is False and after is False
        else "invalid_outcome_pair"
    )
    return {
        "status": label,
        "no_skill": compact_current_condition(no_skill),
        "exact_curated": compact_current_condition(exact),
        "oracle_skill_ids": exact.get("oracle_skill_ids") or [],
        "claim_boundary": "Outcome is primary; strict/process differences are diagnostics.",
    }


def current_unrelated_check(
    exact: dict[str, Any] | None,
    shuffled: dict[str, Any] | None,
) -> dict[str, Any]:
    if exact is None or shuffled is None:
        return {"status": "missing_current_exact_or_shuffled_evidence"}
    if shuffled.get("shuffled_injection_valid") is not True:
        return {
            "status": "invalid_shuffled_skill_injection",
            "exact_curated": compact_current_condition(exact),
            "shuffled_curated": compact_current_condition(shuffled),
            "injection_errors": shuffled.get("shuffled_injection_errors") or [],
        }
    exact_pass = exact.get("outcome_pass")
    shuffled_pass = shuffled.get("outcome_pass")
    status = (
        "single_run_correct_skill_specific"
        if exact_pass is True and shuffled_pass is False
        else "single_run_wrong_skill_insensitive"
        if exact_pass is True and shuffled_pass is True
        else "single_run_shuffled_only_pass"
        if exact_pass is False and shuffled_pass is True
        else "single_run_neither_skill_passes"
        if exact_pass is False and shuffled_pass is False
        else "invalid_outcome_pair"
    )
    return {
        "status": status,
        "exact_curated": compact_current_condition(exact),
        "shuffled_curated": compact_current_condition(shuffled),
        "gold_skill_ids": shuffled.get("shuffled_gold_skill_ids") or [],
        "shuffled_skill_ids": shuffled.get("shuffled_skill_ids") or [],
        "source_environment_id": shuffled.get(
            "shuffled_source_environment_id"
        ),
        "claim_boundary": (
            "The negative control is valid only when equal-count, disjoint, content-bound "
            "injection evidence passes."
        ),
    }


def current_transfer_use_check(
    spec: dict[str, Any],
    current: dict[str, Any],
) -> dict[str, Any]:
    task_id = str(spec["task_id"])
    row = current["evaluation"].get((task_id, "self_generated"))
    if row is None:
        return {"status": "missing_current_self_generated_evaluation"}
    family_skill_ids = {
        str(skill.get("skill_id"))
        for skill in current["skills"]
        if skill.get("family_id") == spec["family_id"] and skill.get("skill_id")
    }
    retrieved = set(map(str, row.get("retrieved_skill_ids") or []))
    used = set(map(str, row.get("skills_actually_used") or []))
    matching_retrieved = sorted(family_skill_ids & retrieved)
    matching_used = sorted(family_skill_ids & used)
    status = (
        "generated_skill_used_on_new_input"
        if matching_used
        else "generated_skill_retrieved_but_not_used"
        if matching_retrieved
        else "no_same_family_generated_skill_visible"
    )
    return {
        "status": status,
        "evidence_revision": "v1.1_current_matrix",
        "family_generated_skill_ids": sorted(family_skill_ids),
        "matching_retrieved_skill_ids": matching_retrieved,
        "matching_used_skill_ids": matching_used,
        "self_generated_condition": compact_current_condition(row),
        "claim_boundary": "Visibility/use is not causal benefit without matched outcomes.",
    }


def enrich_verifier_with_dynamic_flags(
    base: dict[str, Any],
    condition_rows: dict[str, dict[str, Any] | None],
) -> dict[str, Any]:
    rows = [row for row in condition_rows.values() if row is not None]
    process_only = sorted(
        condition
        for condition, row in condition_rows.items()
        if row is not None
        and row.get("outcome_pass") is True
        and row.get("strict_pass") is not True
    )
    all_outcome_fail = bool(rows) and len(rows) == len(CURRENT_CONDITIONS) and all(
        row.get("outcome_pass") is False for row in rows
    )
    result = dict(base)
    result.update(
        {
            "current_condition_count": len(rows),
            "process_only_failure_conditions": process_only,
            "all_four_model_conditions_outcome_fail": all_outcome_fail,
            "model_execution_gap_candidate": bool(
                all_outcome_fail and base.get("reference_strict_pass") is True
            ),
        }
    )
    return result


def current_coverage_errors(
    specs: list[dict[str, Any]],
    current: dict[str, Any],
    reference: dict[str, dict[str, Any]],
    expected_benchmark_revision: str | None,
) -> list[str]:
    errors: list[str] = []
    learning_ids = {
        str(spec["task_id"]) for spec in specs if int(spec["task_index"]) <= 3
    }
    transfer_ids = {
        str(spec["task_id"]) for spec in specs if int(spec["task_index"]) >= 4
    }
    if set(current["learning"]) != learning_ids:
        errors.append(
            "current self-generated learning grid is not the exact 90 T1-T3 tasks"
        )
    for condition in CURRENT_CONDITIONS:
        observed = {
            task_id
            for (task_id, row_condition) in current["evaluation"]
            if row_condition == condition
        }
        if observed != transfer_ids:
            errors.append(
                f"current {condition} grid is not the exact 90 T4-T6 tasks"
            )
    if set(reference) != {str(spec["task_id"]) for spec in specs}:
        errors.append("reference solution grid is not the exact 180 tasks")
    elif any(row.get("strict_pass") is not True for row in reference.values()):
        errors.append("at least one of the 180 reference solutions failed strict verification")

    cells = Counter(
        (
            CONDITION_ALIASES.get(str(row.get("condition")), str(row.get("condition"))),
            str(row.get("environment_id")),
        )
        for row in current["runs"]
    )
    expected_cells = {
        (condition, f"E{environment}")
        for condition in CURRENT_CONDITIONS
        for environment in range(1, 7)
    }
    if set(cells) != expected_cells or any(count != 1 for count in cells.values()):
        errors.append("current run grid is not exactly 4 conditions x 6 environments")
    for run in current["runs"]:
        condition = CONDITION_ALIASES.get(
            str(run.get("condition")), str(run.get("condition"))
        )
        label = f"{condition}/{run.get('environment_id')}"
        if run.get("ap_status") != "Succeeded":
            errors.append(f"{label}: AP status is not Succeeded")
        if run.get("lifecycle_parse_errors"):
            errors.append(f"{label}: lifecycle parse errors are present")
        if run.get("evaluation_task_start_count") != 15:
            errors.append(f"{label}: evaluation start coverage is not 15")
        if run.get("evaluation_task_end_count") != 15:
            errors.append(f"{label}: evaluation end coverage is not 15")
        if run.get("library_frozen_before_evaluation") is not True:
            errors.append(f"{label}: library was not frozen before evaluation")
        if run.get("evaluation_library_hash_stable") is not True:
            errors.append(f"{label}: evaluation library hash was not stable")
        if expected_benchmark_revision and run.get("benchmark_revision") != expected_benchmark_revision:
            errors.append(f"{label}: benchmark revision mismatch")
        if condition == "self_generated":
            if run.get("evaluation_only_t4_t6") is not False:
                errors.append(f"{label}: unexpectedly skipped learning tasks")
            if run.get("learning_record_count") != 15:
                errors.append(f"{label}: learning coverage is not 15")
            if run.get("learning_max_attempts") != 3:
                errors.append(f"{label}: learning attempt budget is not 3")
        elif condition == "no_skill":
            if run.get("baseline") != "no_skill":
                errors.append(f"{label}: baseline is not no_skill")
        elif condition == "exact_curated":
            if run.get("oracle_skill_view") is not True:
                errors.append(f"{label}: exact oracle view is not enabled")
        elif condition == "shuffled_curated":
            if run.get("shuffled_skill_view") is not True:
                errors.append(f"{label}: shuffled view is not enabled")

    for task_id in transfer_ids:
        no_skill = current["evaluation"].get((task_id, "no_skill"))
        exact = current["evaluation"].get((task_id, "exact_curated"))
        shuffled = current["evaluation"].get((task_id, "shuffled_curated"))
        if no_skill is not None and no_skill.get("no_skill_empty") is not True:
            errors.append(f"{task_id}: no-skill evidence is not empty")
        if exact is not None and exact.get("oracle_injection_exact") is not True:
            errors.append(f"{task_id}: exact curated injection is invalid")
        if (
            shuffled is not None
            and shuffled.get("shuffled_injection_valid") is not True
        ):
            errors.append(f"{task_id}: shuffled curated injection is invalid")
    return errors


def build(args: argparse.Namespace) -> dict[str, Any]:
    specs = load_specs(args.tasks_root)
    static_raw = load_json(args.static_audit)
    static_by_id = {str(row["task_id"]): row for row in static_raw.get("tasks", [])}
    if set(static_by_id) != {str(row["task_id"]) for row in specs}:
        raise ValueError("static audit does not cover the exact 180-task spec set")
    behavior = behavior_index(load_json(args.legacy_behavior))
    legacy_report = load_json(args.legacy_t56_report)
    measurements = measurement_index(legacy_report)
    comparisons = comparison_index(legacy_report)
    task_audit = load_json(args.v11_task_audit)
    repaired_ids = {
        str(row["task_id"])
        for row in task_audit.get("outcome_or_contract_repairs", [])
    }
    reference = reference_index(load_json(args.v11_reference_audit))
    current_pairs = load_current_pairs(load_json(args.v11_regression))
    full_evidence_path = getattr(args, "v11_full_evidence", None)
    expected_model = getattr(args, "expected_model", "qwen3.7-max")
    expected_benchmark_revision = getattr(
        args, "expected_benchmark_revision", None
    )
    current = (
        current_evidence_index(load_json(full_evidence_path), expected_model)
        if full_evidence_path is not None
        else None
    )
    coverage_errors = (
        current_coverage_errors(
            specs,
            current,
            reference,
            expected_benchmark_revision,
        )
        if current is not None
        else ["current v1.1 four-condition evidence was not provided"]
    )
    if getattr(args, "require_complete_current", False) and coverage_errors:
        raise ValueError(
            "current evidence completeness validation failed: "
            + "; ".join(coverage_errors)
        )

    tasks: list[dict[str, Any]] = []
    for spec in specs:
        task_id = str(spec["task_id"])
        tier = int(spec["task_index"])
        legacy_conditions = legacy_condition_rows(comparisons.get(task_id, []))
        legacy_need = check_need(
            tier,
            measurements.get(task_id, []),
            legacy_conditions,
            current_pairs.get(task_id),
        )
        checks = {
            "1_experience_generation_and_reuse": check_experience(spec, behavior),
            "2_historical_skill_demand": legacy_need,
            "3_correct_expert_skill_effect": check_expert(tier, legacy_conditions),
            "4_unrelated_skill_negative_control": check_unrelated(tier),
            "5_task_and_verifier_validity": check_verifier(
                spec,
                static_by_id[task_id],
                reference.get(task_id),
                task_id in repaired_ids,
            ),
        }
        if current is not None and tier <= 3:
            checks["1_experience_generation_and_reuse"] = current_experience_check(
                spec, current
            )
        elif current is not None:
            condition_rows = {
                condition: current["evaluation"].get((task_id, condition))
                for condition in CURRENT_CONDITIONS
            }
            checks["1_experience_generation_and_reuse"] = (
                current_transfer_use_check(spec, current)
            )
            checks["2_historical_skill_demand"] = current_need_check(
                condition_rows["no_skill"], legacy_need
            )
            checks["3_correct_expert_skill_effect"] = current_expert_check(
                condition_rows["no_skill"], condition_rows["exact_curated"]
            )
            checks["4_unrelated_skill_negative_control"] = (
                current_unrelated_check(
                    condition_rows["exact_curated"],
                    condition_rows["shuffled_curated"],
                )
            )
            checks["5_task_and_verifier_validity"] = (
                enrich_verifier_with_dynamic_flags(
                    checks["5_task_and_verifier_validity"], condition_rows
                )
            )

        if tier <= 3:
            learning_ready = current is not None and task_id in current["learning"]
            reference_ready = (
                task_id in reference
                and reference[task_id].get("strict_pass") is True
            )
            readiness = (
                "ready"
                if learning_ready and reference_ready
                else "insufficient_current_learning_or_reference_evidence"
            )
        else:
            rows = (
                {
                    condition: current["evaluation"].get((task_id, condition))
                    for condition in CURRENT_CONDITIONS
                }
                if current is not None
                else {condition: None for condition in CURRENT_CONDITIONS}
            )
            controls_ready = all(row is not None for row in rows.values())
            injection_ready = bool(
                rows["no_skill"]
                and rows["no_skill"].get("no_skill_empty") is True
                and rows["exact_curated"]
                and rows["exact_curated"].get("oracle_injection_exact") is True
                and rows["shuffled_curated"]
                and rows["shuffled_curated"].get("shuffled_injection_valid") is True
            )
            reference_ready = (
                task_id in reference
                and reference[task_id].get("strict_pass") is True
            )
            readiness = (
                "ready"
                if controls_ready and injection_ready and reference_ready
                else "insufficient_current_four_condition_or_reference_evidence"
            )
        tasks.append(
            {
                "task_id": task_id,
                "task_slug": spec.get("task_slug"),
                "environment_id": spec.get("environment_id"),
                "family_id": spec.get("family_id"),
                "tier": tier,
                "role": spec.get("role"),
                "phase": spec.get("phase"),
                "primary_skill": spec.get("primary_skill"),
                "required_skills": spec.get("required_skills") or [],
                "composition_type": spec.get("composition_type"),
                "instruction_path": spec.get("instruction_path"),
                "instruction_sha256": spec.get("instruction_sha256"),
                "instruction": spec.get("instruction"),
                "readiness": readiness,
                "checks": checks,
            }
        )

    current_evaluation = current["evaluation"] if current is not None else {}
    summary = {
        "task_count": len(tasks),
        "planned_task_condition_cells": 630,
        "task_attempt_range_with_learning_retries": [630, 810],
        "by_tier": dict(sorted(Counter(f"T{row['tier']}" for row in tasks).items())),
        "static_verifier_coverage": sum(
            bool(row["checks"]["5_task_and_verifier_validity"])
            for row in tasks
        ),
        "legacy_learning_task_observations": 90 * len({model for _, model in behavior}),
        "v1_1_current_learning_coverage": (
            len(current["learning"]) if current is not None else 0
        ),
        "v1_1_matched_selfgen_no_skill_coverage": sum(
            (task_id, "self_generated") in current_evaluation
            and (task_id, "no_skill") in current_evaluation
            for task_id in {
                str(spec["task_id"])
                for spec in specs
                if int(spec["task_index"]) >= 4
            }
        ),
        "v1_1_exact_curated_coverage": sum(
            condition == "exact_curated"
            for _, condition in current_evaluation
        ),
        "v1_1_shuffled_curated_coverage": sum(
            condition == "shuffled_curated"
            for _, condition in current_evaluation
        ),
        "v1_1_reference_solution_coverage": len(reference),
        "current_evidence_complete": not coverage_errors,
        "current_evidence_errors": coverage_errors,
        "ready_for_final_five_point_decision": sum(
            row["readiness"] == "ready" for row in tasks
        ),
        "high_process_shape_review": sum(
            row["checks"]["5_task_and_verifier_validity"]["process_shape_sensitivity"]
            == "high"
            for row in tasks
        ),
    }
    return {
        "schema_version": "2.0" if current is not None else "1.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "benchmark_revision": revision(args.tasks_root.parents[1]),
        "claim_boundary": (
            "Current matched rows are a first-pass screen, not a stable causal estimate. "
            "Legacy v1 results remain diagnostic only; outcome-flip and critical rows need "
            "valid repeats before a majority label."
            if current is not None
            else "This is a coverage and evidence ledger. Legacy v1 results do not complete "
            "v1.1 causal cells, and missing shuffled controls remain missing."
        ),
        "inputs": {
            name: str(getattr(args, name).resolve())
            for name in (
                "tasks_root",
                "static_audit",
                "legacy_behavior",
                "legacy_t56_report",
                "v11_task_audit",
                "v11_reference_audit",
                "v11_regression",
            )
        }
        | (
            {"v11_full_evidence": str(full_evidence_path.resolve())}
            if full_evidence_path is not None
            else {}
        ),
        "summary": summary,
        "tasks": tasks,
    }


def write_csv(path: Path, tasks: list[dict[str, Any]]) -> None:
    columns = [
        "task_id",
        "environment_id",
        "family_id",
        "tier",
        "role",
        "task_slug",
        "readiness",
        "point1_status",
        "point2_status",
        "point3_status",
        "point4_status",
        "point5_status",
        "process_shape_sensitivity",
        "reference_strict_pass",
        "known_v1_repair_applied",
        "instruction_path",
    ]
    handle = io.StringIO(newline="")
    writer = csv.DictWriter(handle, fieldnames=columns)
    writer.writeheader()
    for task in tasks:
        checks = task["checks"]
        verifier = checks["5_task_and_verifier_validity"]
        writer.writerow(
            {
                "task_id": task["task_id"],
                "environment_id": task["environment_id"],
                "family_id": task["family_id"],
                "tier": task["tier"],
                "role": task["role"],
                "task_slug": task["task_slug"],
                "readiness": task["readiness"],
                "point1_status": checks["1_experience_generation_and_reuse"]["status"],
                "point2_status": checks["2_historical_skill_demand"]["status"],
                "point3_status": checks["3_correct_expert_skill_effect"]["status"],
                "point4_status": checks["4_unrelated_skill_negative_control"]["status"],
                "point5_status": verifier["status"],
                "process_shape_sensitivity": verifier["process_shape_sensitivity"],
                "reference_strict_pass": verifier["reference_strict_pass"],
                "known_v1_repair_applied": verifier["known_v1_repair_applied"],
                "instruction_path": task["instruction_path"],
            }
        )
    atomic_text(path, handle.getvalue())


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--tasks-root", type=Path, required=True)
    parser.add_argument("--static-audit", type=Path, required=True)
    parser.add_argument("--legacy-behavior", type=Path, required=True)
    parser.add_argument("--legacy-t56-report", type=Path, required=True)
    parser.add_argument("--v11-task-audit", type=Path, required=True)
    parser.add_argument("--v11-reference-audit", type=Path, required=True)
    parser.add_argument("--v11-regression", type=Path, required=True)
    parser.add_argument(
        "--v11-full-evidence",
        type=Path,
        help="current v1.1 four-condition collector output",
    )
    parser.add_argument("--expected-model", default="qwen3.7-max")
    parser.add_argument("--expected-benchmark-revision")
    parser.add_argument(
        "--require-complete-current",
        action="store_true",
        help="fail unless all 180 reference and matched current evidence cells validate",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    result = build(args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "task_five_point_audit.json"
    csv_path = args.output_dir / "task_five_point_audit.csv"
    atomic_text(json_path, json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    write_csv(csv_path, result["tasks"])
    print(json.dumps({"json": str(json_path.resolve()), "csv": str(csv_path.resolve()), **result["summary"]}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
