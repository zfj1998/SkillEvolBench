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
    elif tier >= 4 and reference:
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

    tasks: list[dict[str, Any]] = []
    for spec in specs:
        task_id = str(spec["task_id"])
        tier = int(spec["task_index"])
        legacy_conditions = legacy_condition_rows(comparisons.get(task_id, []))
        checks = {
            "1_experience_generation_and_reuse": check_experience(spec, behavior),
            "2_historical_skill_demand": check_need(
                tier,
                measurements.get(task_id, []),
                legacy_conditions,
                current_pairs.get(task_id),
            ),
            "3_correct_expert_skill_effect": check_expert(tier, legacy_conditions),
            "4_unrelated_skill_negative_control": check_unrelated(tier),
            "5_task_and_verifier_validity": check_verifier(
                spec,
                static_by_id[task_id],
                reference.get(task_id),
                task_id in repaired_ids,
            ),
        }
        if tier <= 3:
            readiness = "learning_observable_but_v1_1_reference_not_run"
        else:
            readiness = "insufficient_causal_evidence_missing_v1_1_four_conditions"
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

    summary = {
        "task_count": len(tasks),
        "by_tier": dict(sorted(Counter(f"T{row['tier']}" for row in tasks).items())),
        "static_verifier_coverage": sum(
            bool(row["checks"]["5_task_and_verifier_validity"])
            for row in tasks
        ),
        "legacy_learning_task_observations": 90 * len({model for _, model in behavior}),
        "v1_1_reference_solution_coverage": len(reference),
        "v1_1_matched_selfgen_no_skill_coverage": len(current_pairs),
        "v1_1_exact_curated_coverage": 0,
        "v1_1_shuffled_curated_coverage": 0,
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
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "benchmark_revision": revision(args.tasks_root.parents[1]),
        "claim_boundary": (
            "This is a coverage and evidence ledger. Legacy v1 results do not complete v1.1 "
            "causal cells, and missing shuffled controls remain missing."
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
        },
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
