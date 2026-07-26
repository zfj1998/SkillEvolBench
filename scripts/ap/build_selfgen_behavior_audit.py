#!/usr/bin/env python3
"""Build an evidence-grounded audit of self-generated skill behavior.

The output deliberately separates:

* acquisition: T1-T3 attempts and terminal verifier results;
* creation: active skill files and their version summaries;
* utilization: T4-T6 skill reads and verifier results; and
* paired behavior: same-task differences between two selected models.

It does not infer that a read skill caused a pass.  Causal claims require a
matched no-skill control, which this descriptive audit does not provide.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from statistics import median
from typing import Any


VERIFIER_MARKER = re.compile(
    r"\b(?:verifier|hidden tests?|process tests?|source scan|grep|literal|"
    r"regex|static analysis|rubric)\b",
    re.IGNORECASE,
)


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise TypeError(f"{path} must contain a JSON object")
    return value


def family_id_for_task(task_id: str) -> str:
    match = re.match(r"^(E\d+-LS\d+)-T[1-6]$", task_id)
    if not match:
        raise ValueError(f"unexpected task id: {task_id}")
    return match.group(1)


def selected_selfgen(row: dict[str, Any], model: str) -> bool:
    return (
        row.get("selected_run", True)
        and row.get("condition") == "self_generated"
        and row.get("model") == model
    )


def pass_count(rows: list[dict[str, Any]], key: str) -> int:
    return sum(row.get(key) is True for row in rows)


def failure_names(row: dict[str, Any]) -> list[str]:
    result = []
    for item in row.get("failed_tests") or []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
        else:
            name = str(item).strip()
        if name:
            result.append(name)
    return result


def same_family_skill_used(row: dict[str, Any]) -> bool:
    family_id = str(row.get("family_id") or family_id_for_task(str(row["task_id"])))
    return any(
        str(skill_id).split(".", 1)[0] == family_id
        for skill_id in row.get("skills_actually_used") or []
    )


def metric_state(left: bool, right: bool, left_name: str, right_name: str) -> str:
    if left and right:
        return "both_pass"
    if left:
        return f"{left_name}_only"
    if right:
        return f"{right_name}_only"
    return "both_fail"


def reflection_rejection_reason(
    row: dict[str, Any], raw_root: Path | None
) -> str | None:
    if row.get("reflection_status") != "rejected" or raw_root is None:
        return None
    relative = row.get("local_reflection_path")
    if not relative:
        return None
    path = raw_root / str(relative) / "self_reflection_result.json"
    if not path.is_file():
        return None
    try:
        value = load_json(path)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return None
    reason = str(value.get("reason") or "").strip()
    return reason or None


def build_model_summary(
    model: str,
    learning: list[dict[str, Any]],
    skills: list[dict[str, Any]],
    evaluation: list[dict[str, Any]],
    raw_root: Path | None,
) -> dict[str, Any]:
    skill_chars = sorted(
        int(row.get("generated_chars") or len(str(row.get("generated_text") or "")))
        for row in skills
    )
    reflection_states = Counter(
        str(row.get("reflection_status") or "missing") for row in learning
    )
    reflection_rejection_reasons = Counter(
        reason
        for row in learning
        if (reason := reflection_rejection_reason(row, raw_root))
    )
    by_tier = []
    for tier in range(1, 7):
        rows = (
            [row for row in learning if int(row.get("tier") or 0) == tier]
            if tier <= 3
            else [row for row in evaluation if int(row.get("tier") or 0) == tier]
        )
        if tier <= 3:
            by_tier.append(
                {
                    "tier": tier,
                    "n": len(rows),
                    "initial_pass": pass_count(rows, "initial_verifier_passed"),
                    "terminal_pass": pass_count(rows, "terminal_verifier_passed"),
                    "attempts": sum(int(row.get("learning_attempts") or 0) for row in rows),
                }
            )
        else:
            by_tier.append(
                {
                    "tier": tier,
                    "n": len(rows),
                    "strict_pass": pass_count(rows, "strict_pass"),
                    "outcome_pass": pass_count(rows, "outcome_pass"),
                    "process_pass": pass_count(rows, "process_pass"),
                    "any_skill_used": sum(bool(row.get("skills_actually_used")) for row in rows),
                    "same_family_skill_used": sum(
                        same_family_skill_used(row) for row in rows
                    ),
                }
            )
    return {
        "model": model,
        "learning_tasks": len(learning),
        "learning_attempts": sum(
            int(row.get("learning_attempts") or 0) for row in learning
        ),
        "initial_passes": pass_count(learning, "initial_verifier_passed"),
        "terminal_passes": pass_count(learning, "terminal_verifier_passed"),
        "repaired_to_pass": pass_count(learning, "repaired_to_pass"),
        "same_session_verified": sum(
            row.get("all_attempts_same_session_verified") is True for row in learning
        ),
        "reflection_status_counts": dict(sorted(reflection_states.items())),
        "reflection_rejection_reason_counts": dict(
            sorted(reflection_rejection_reasons.items())
        ),
        "active_skills": len(skills),
        "families_with_active_skill": len(
            {str(row.get("family_id")) for row in skills}
        ),
        "skills_with_multiple_versions": sum(
            len(row.get("version_summaries") or []) > 1 for row in skills
        ),
        "total_skill_versions": sum(
            len(row.get("version_summaries") or []) for row in skills
        ),
        "median_skill_chars": median(skill_chars) if skill_chars else None,
        "skills_with_verifier_markers": sum(
            bool(VERIFIER_MARKER.search(str(row.get("generated_text") or "")))
            for row in skills
        ),
        "evaluation_tasks": len(evaluation),
        "evaluation_strict_passes": pass_count(evaluation, "strict_pass"),
        "evaluation_outcome_passes": pass_count(evaluation, "outcome_pass"),
        "evaluation_process_passes": pass_count(evaluation, "process_pass"),
        "evaluation_any_skill_used": sum(
            bool(row.get("skills_actually_used")) for row in evaluation
        ),
        "evaluation_same_family_skill_used": sum(
            same_family_skill_used(row) for row in evaluation
        ),
        "by_tier": by_tier,
    }


def compact_learning(
    row: dict[str, Any], raw_root: Path | None
) -> dict[str, Any]:
    return {
        "task_id": row.get("task_id"),
        "tier": row.get("tier"),
        "attempts": int(row.get("learning_attempts") or 0),
        "initial_pass": row.get("initial_verifier_passed") is True,
        "terminal_pass": row.get("terminal_verifier_passed") is True,
        "repaired_to_pass": row.get("repaired_to_pass") is True,
        "same_session_verified": row.get("all_attempts_same_session_verified")
        is True,
        "reflection_mode": row.get("reflection_mode"),
        "reflection_status": row.get("reflection_status"),
        "reflection_rejection_reason": reflection_rejection_reason(row, raw_root),
        "failed_tests": failure_names(row),
    }


def compact_skill(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "skill_id": row.get("skill_id"),
        "skill_slug": row.get("skill_slug"),
        "current_version": row.get("current_version"),
        "created_at_task": row.get("created_at_task"),
        "last_revised_at_task": row.get("last_revised_at_task"),
        "generated_chars": row.get("generated_chars"),
        "description": row.get("generated_description"),
        "headings": row.get("generated_headings") or [],
        "version_summaries": row.get("version_summaries") or [],
        "generated_path": row.get("generated_path"),
        "verifier_marker_hits": len(
            VERIFIER_MARKER.findall(str(row.get("generated_text") or ""))
        ),
    }


def compact_evaluation(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "task_id": row.get("task_id"),
        "tier": row.get("tier"),
        "strict_pass": row.get("strict_pass") is True,
        "outcome_pass": row.get("outcome_pass") is True,
        "process_pass": row.get("process_pass") is True,
        "skills_retrieved": row.get("retrieved_skill_ids") or [],
        "skills_actually_used": row.get("skills_actually_used") or [],
        "same_family_skill_used": same_family_skill_used(row),
        "failed_tests": failure_names(row),
        "trajectory_path": row.get("local_trajectory_path"),
        "artifact_path": row.get("local_artifact_task_path"),
    }


def build_audit(
    evidence: dict[str, Any],
    left_model: str,
    right_model: str,
    raw_root: Path | None,
) -> dict[str, Any]:
    models = (left_model, right_model)
    learning_by_model: dict[str, list[dict[str, Any]]] = {}
    skills_by_model: dict[str, list[dict[str, Any]]] = {}
    eval_by_model: dict[str, list[dict[str, Any]]] = {}
    for model in models:
        learning_by_model[model] = sorted(
            [
                row
                for row in evidence.get("learning_tasks", [])
                if isinstance(row, dict) and selected_selfgen(row, model)
            ],
            key=lambda row: str(row.get("task_id") or ""),
        )
        skills_by_model[model] = sorted(
            [
                row
                for row in evidence.get("skills", [])
                if isinstance(row, dict) and selected_selfgen(row, model)
            ],
            key=lambda row: (
                str(row.get("family_id") or ""),
                str(row.get("skill_id") or ""),
            ),
        )
        eval_by_model[model] = sorted(
            [
                row
                for row in evidence.get("tasks", [])
                if isinstance(row, dict) and selected_selfgen(row, model)
            ],
            key=lambda row: str(row.get("task_id") or ""),
        )

    families = sorted(
        {
            str(row.get("family_id") or family_id_for_task(str(row["task_id"])))
            for model in models
            for row in learning_by_model[model] + eval_by_model[model]
        }
    )
    family_rows = []
    for family_id in families:
        by_model = {}
        for model in models:
            family_learning = [
                compact_learning(row, raw_root)
                for row in learning_by_model[model]
                if str(row.get("family_id")) == family_id
            ]
            family_skills = [
                compact_skill(row)
                for row in skills_by_model[model]
                if str(row.get("family_id")) == family_id
            ]
            family_eval = [
                compact_evaluation(row)
                for row in eval_by_model[model]
                if str(row.get("family_id")) == family_id
            ]
            by_model[model] = {
                "learning": family_learning,
                "skills": family_skills,
                "evaluation": family_eval,
                "terminal_learning_passes": sum(
                    row["terminal_pass"] for row in family_learning
                ),
                "learning_attempts": sum(row["attempts"] for row in family_learning),
                "active_skill_count": len(family_skills),
                "evaluation_strict_passes": sum(
                    row["strict_pass"] for row in family_eval
                ),
                "evaluation_outcome_passes": sum(
                    row["outcome_pass"] for row in family_eval
                ),
                "same_family_skill_reads": sum(
                    row["same_family_skill_used"] for row in family_eval
                ),
            }
        family_rows.append(
            {
                "family_id": family_id,
                "environment_id": family_id.split("-", 1)[0],
                "models": by_model,
            }
        )

    evaluation_index = {
        (model, str(row["task_id"])): row
        for model in models
        for row in eval_by_model[model]
    }
    task_ids = sorted(
        set(row.get("task_id") for row in eval_by_model[left_model])
        & set(row.get("task_id") for row in eval_by_model[right_model])
    )
    paired_tasks = []
    for task_id in task_ids:
        left = evaluation_index[(left_model, str(task_id))]
        right = evaluation_index[(right_model, str(task_id))]
        paired_tasks.append(
            {
                "task_id": task_id,
                "family_id": left.get("family_id"),
                "tier": left.get("tier"),
                "strict_state": metric_state(
                    left.get("strict_pass") is True,
                    right.get("strict_pass") is True,
                    left_model,
                    right_model,
                ),
                "outcome_state": metric_state(
                    left.get("outcome_pass") is True,
                    right.get("outcome_pass") is True,
                    left_model,
                    right_model,
                ),
                "process_state": metric_state(
                    left.get("process_pass") is True,
                    right.get("process_pass") is True,
                    left_model,
                    right_model,
                ),
                left_model: compact_evaluation(left),
                right_model: compact_evaluation(right),
            }
        )

    pair_summaries = {}
    for metric in ("strict", "outcome", "process"):
        pair_summaries[metric] = dict(
            sorted(Counter(row[f"{metric}_state"] for row in paired_tasks).items())
        )

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "evidence_inventory_path": evidence.get("inventory_path"),
        "models": list(models),
        "claim_boundary": (
            "Skill reads prove utilization/adherence, not causal usefulness. "
            "Pass-rate attribution requires matched no-skill controls and a "
            "task/verifier validity audit."
        ),
        "model_summaries": {
            model: build_model_summary(
                model,
                learning_by_model[model],
                skills_by_model[model],
                eval_by_model[model],
                raw_root,
            )
            for model in models
        },
        "paired_summary": {
            "matched_tasks": len(paired_tasks),
            **pair_summaries,
        },
        "families": family_rows,
        "paired_tasks": paired_tasks,
    }


def write_family_csv(path: Path, audit: dict[str, Any]) -> None:
    models = audit["models"]
    columns = ["family_id", "environment_id"]
    for model in models:
        columns.extend(
            [
                f"{model}_learning_attempts",
                f"{model}_terminal_learning_passes",
                f"{model}_active_skills",
                f"{model}_skill_versions",
                f"{model}_t4_t6_strict_passes",
                f"{model}_t4_t6_outcome_passes",
                f"{model}_same_family_skill_reads",
            ]
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for family in audit["families"]:
            row: dict[str, Any] = {
                "family_id": family["family_id"],
                "environment_id": family["environment_id"],
            }
            for model in models:
                item = family["models"][model]
                row.update(
                    {
                        f"{model}_learning_attempts": item["learning_attempts"],
                        f"{model}_terminal_learning_passes": item[
                            "terminal_learning_passes"
                        ],
                        f"{model}_active_skills": item["active_skill_count"],
                        f"{model}_skill_versions": sum(
                            len(skill["version_summaries"])
                            for skill in item["skills"]
                        ),
                        f"{model}_t4_t6_strict_passes": item[
                            "evaluation_strict_passes"
                        ],
                        f"{model}_t4_t6_outcome_passes": item[
                            "evaluation_outcome_passes"
                        ],
                        f"{model}_same_family_skill_reads": item[
                            "same_family_skill_reads"
                        ],
                    }
                )
            writer.writerow(row)


def write_task_csv(path: Path, audit: dict[str, Any]) -> None:
    models = audit["models"]
    columns = [
        "task_id",
        "family_id",
        "tier",
        "strict_state",
        "outcome_state",
        "process_state",
    ]
    for model in models:
        columns.extend(
            [
                f"{model}_strict",
                f"{model}_outcome",
                f"{model}_process",
                f"{model}_same_family_skill_used",
                f"{model}_failed_tests",
            ]
        )
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for item in audit["paired_tasks"]:
            row = {key: item[key] for key in columns[:6]}
            for model in models:
                result = item[model]
                row.update(
                    {
                        f"{model}_strict": result["strict_pass"],
                        f"{model}_outcome": result["outcome_pass"],
                        f"{model}_process": result["process_pass"],
                        f"{model}_same_family_skill_used": result[
                            "same_family_skill_used"
                        ],
                        f"{model}_failed_tests": ";".join(result["failed_tests"]),
                    }
                )
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--left-model", default="sig-fable")
    parser.add_argument("--right-model", default="opus-4.8")
    parser.add_argument("--raw-root", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    evidence = load_json(args.evidence)
    audit = build_audit(
        evidence, args.left_model, args.right_model, args.raw_root
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "selfgen_behavior_audit.json"
    family_csv = args.output_dir / "selfgen_family_audit.csv"
    task_csv = args.output_dir / "selfgen_paired_tasks.csv"
    json_path.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    write_family_csv(family_csv, audit)
    write_task_csv(task_csv, audit)
    print(
        json.dumps(
            {
                "json": str(json_path.resolve()),
                "family_csv": str(family_csv.resolve()),
                "task_csv": str(task_csv.resolve()),
                "matched_tasks": audit["paired_summary"]["matched_tasks"],
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
