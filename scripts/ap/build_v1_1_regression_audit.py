#!/usr/bin/env python3
"""Build the matched Opus v1.1 self-generated versus no-skill audit.

The input is the normalized evidence produced by ``build_t56_oracle_study.py``.
Jobs are selected by their exact AP job IDs so an older run of the same model,
environment, and condition cannot silently replace the v1.1 regression.

This audit separates three questions:

* acquisition: did T1-T3 pass after same-session retries, and what was created?
* utilization: which generated skills were actually read during T4-T6?
* usefulness: on the same T4-T6 task, did self-generated beat no-skill?

The last question is reported as paired observations, not as a general causal
claim beyond this one model run.
"""

from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


METRICS = ("strict", "outcome", "process")


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def passed(row: dict[str, Any], metric: str) -> bool:
    return row.get(f"{metric}_pass") is True


def failed_test_names(row: dict[str, Any]) -> list[str]:
    names: list[str] = []
    for item in row.get("failed_tests") or []:
        if isinstance(item, dict):
            value = item.get("name")
        else:
            value = item
        if value:
            names.append(str(value))
    return names


def paired_state(selfgen: bool, no_skill: bool) -> str:
    if selfgen and no_skill:
        return "both_pass"
    if selfgen:
        return "skill_rescue"
    if no_skill:
        return "skill_harm"
    return "both_fail"


def compact_task(row: dict[str, Any], *, include_skills: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "strict_pass": passed(row, "strict"),
        "outcome_pass": passed(row, "outcome"),
        "process_pass": passed(row, "process"),
        "failed_tests": failed_test_names(row),
        "classification": row.get("classification"),
        "trajectory_path": row.get("local_trajectory_path"),
        "artifact_path": row.get("local_artifact_task_path"),
    }
    if include_skills:
        result.update(
            {
                "skills_retrieved": row.get("retrieved_skill_ids") or [],
                "skills_actually_used": row.get("skills_actually_used") or [],
            }
        )
    return result


def summarize_tasks(rows: list[dict[str, Any]], *, include_skills: bool) -> dict[str, Any]:
    by_tier = []
    for tier in (4, 5, 6):
        selected = [row for row in rows if int(row.get("tier") or 0) == tier]
        by_tier.append(
            {
                "tier": tier,
                "n": len(selected),
                **{
                    f"{metric}_pass": sum(passed(row, metric) for row in selected)
                    for metric in METRICS
                },
                **(
                    {
                        "any_skill_read": sum(
                            bool(row.get("skills_actually_used")) for row in selected
                        )
                    }
                    if include_skills
                    else {}
                ),
            }
        )
    summary = {
        "n": len(rows),
        **{
            f"{metric}_pass": sum(passed(row, metric) for row in rows)
            for metric in METRICS
        },
        "by_tier": by_tier,
    }
    if include_skills:
        summary["any_skill_read"] = sum(
            bool(row.get("skills_actually_used")) for row in rows
        )
    return summary


def summarize_learning(rows: list[dict[str, Any]], skills: list[dict[str, Any]]) -> dict[str, Any]:
    reflection_counts = Counter(
        str(row.get("reflection_status") or "missing") for row in rows
    )
    return {
        "tasks": len(rows),
        "attempts": sum(int(row.get("learning_attempts") or 0) for row in rows),
        "initial_pass": sum(
            row.get("initial_verifier_passed") is True for row in rows
        ),
        "terminal_pass": sum(
            row.get("terminal_verifier_passed") is True for row in rows
        ),
        "repaired_to_pass": sum(row.get("repaired_to_pass") is True for row in rows),
        "same_session_verified": sum(
            row.get("all_attempts_same_session_verified") is True for row in rows
        ),
        "reflection_status_counts": dict(sorted(reflection_counts.items())),
        "active_skills": len(skills),
        "skill_versions": sum(
            len(row.get("version_summaries") or []) for row in skills
        ),
        "skills": [
            {
                "skill_id": row.get("skill_id"),
                "family_id": row.get("family_id"),
                "current_version": row.get("current_version"),
                "generated_chars": row.get("generated_chars"),
                "description": row.get("generated_description"),
                "generated_text": row.get("generated_text"),
                "version_summaries": row.get("version_summaries") or [],
                "generated_path": row.get("generated_path"),
            }
            for row in sorted(
                skills,
                key=lambda item: (
                    str(item.get("family_id") or ""),
                    str(item.get("skill_id") or ""),
                ),
            )
        ],
        "task_records": [
            {
                "task_id": row.get("task_id"),
                "tier": row.get("tier"),
                "attempts": int(row.get("learning_attempts") or 0),
                "initial_pass": row.get("initial_verifier_passed") is True,
                "terminal_pass": row.get("terminal_verifier_passed") is True,
                "repaired_to_pass": row.get("repaired_to_pass") is True,
                "same_session_verified": (
                    row.get("all_attempts_same_session_verified") is True
                ),
                "reflection_status": row.get("reflection_status"),
                "failed_tests": failed_test_names(row),
                "trajectory_path": row.get("local_trajectory_path"),
                "reflection_path": row.get("local_reflection_path"),
            }
            for row in sorted(rows, key=lambda item: str(item.get("task_id") or ""))
        ],
    }


def build_audit(
    evidence: dict[str, Any],
    *,
    selfgen_job_id: str,
    no_skill_job_id: str,
    environment_id: str,
    split: str,
) -> dict[str, Any]:
    tasks = [row for row in evidence.get("tasks", []) if isinstance(row, dict)]
    learning = [
        row for row in evidence.get("learning_tasks", []) if isinstance(row, dict)
    ]
    skills = [row for row in evidence.get("skills", []) if isinstance(row, dict)]

    selfgen_rows = sorted(
        [
            row
            for row in tasks
            if row.get("job_id") == selfgen_job_id
            and row.get("environment_id") == environment_id
            and row.get("selected_run") is True
        ],
        key=lambda row: str(row.get("task_id") or ""),
    )
    no_skill_rows = sorted(
        [
            row
            for row in tasks
            if row.get("job_id") == no_skill_job_id
            and row.get("environment_id") == environment_id
            and row.get("selected_run") is True
        ],
        key=lambda row: str(row.get("task_id") or ""),
    )
    expected = {
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in range(4, 7)
    }
    selfgen_ids = {str(row.get("task_id")) for row in selfgen_rows}
    no_skill_ids = {str(row.get("task_id")) for row in no_skill_rows}
    if selfgen_ids != expected:
        raise ValueError(
            f"self-generated job has {len(selfgen_ids)}/15 expected tasks; "
            f"missing={sorted(expected - selfgen_ids)}"
        )
    if no_skill_ids != expected:
        raise ValueError(
            f"no-skill job has {len(no_skill_ids)}/15 expected tasks; "
            f"missing={sorted(expected - no_skill_ids)}"
        )

    selfgen_index = {str(row["task_id"]): row for row in selfgen_rows}
    no_skill_index = {str(row["task_id"]): row for row in no_skill_rows}
    paired_tasks = []
    paired_summary = {metric: Counter() for metric in METRICS}
    for task_id in sorted(expected):
        selfgen = selfgen_index[task_id]
        no_skill = no_skill_index[task_id]
        states = {
            metric: paired_state(passed(selfgen, metric), passed(no_skill, metric))
            for metric in METRICS
        }
        for metric, state in states.items():
            paired_summary[metric][state] += 1
        paired_tasks.append(
            {
                "task_id": task_id,
                "family_id": selfgen.get("family_id"),
                "tier": int(selfgen.get("tier") or 0),
                "states": states,
                "self_generated": compact_task(selfgen, include_skills=True),
                "no_skill": compact_task(no_skill, include_skills=False),
            }
        )

    selected_learning = sorted(
        [
            row
            for row in learning
            if row.get("job_id") == selfgen_job_id
            and row.get("environment_id") == environment_id
            and row.get("selected_run") is True
        ],
        key=lambda row: str(row.get("task_id") or ""),
    )
    selected_skills = [
        row
        for row in skills
        if row.get("job_id") == selfgen_job_id
        and row.get("environment_id") == environment_id
        and row.get("selected_run") is True
    ]
    if len(selected_learning) != 15:
        raise ValueError(
            f"self-generated job has {len(selected_learning)}/15 T1-T3 learning records"
        )

    return {
        "schema_version": 1,
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "split": split,
        "environment_id": environment_id,
        "model": "Opus 4.8",
        "jobs": {
            "self_generated": selfgen_job_id,
            "no_skill": no_skill_job_id,
        },
        "claim_boundary": (
            "This is one matched run per condition. A skill read proves "
            "utilization; task-level skill rescue/harm is a paired observation, "
            "not a population-level causal estimate."
        ),
        "learning": summarize_learning(selected_learning, selected_skills),
        "self_generated": summarize_tasks(selfgen_rows, include_skills=True),
        "no_skill": summarize_tasks(no_skill_rows, include_skills=False),
        "paired_summary": {
            metric: dict(sorted(counter.items()))
            for metric, counter in paired_summary.items()
        },
        "paired_tasks": paired_tasks,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence", type=Path, required=True)
    parser.add_argument("--selfgen-job-id", required=True)
    parser.add_argument("--no-skill-job-id", required=True)
    parser.add_argument("--environment-id", default="E6")
    parser.add_argument("--split", default="v1.1@1")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    audit = build_audit(
        load_json(args.evidence),
        selfgen_job_id=args.selfgen_job_id,
        no_skill_job_id=args.no_skill_job_id,
        environment_id=args.environment_id,
        split=args.split,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output.resolve())
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
