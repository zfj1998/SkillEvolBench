#!/usr/bin/env python3
"""Aggregate and validate a six-environment AP reference-solution export."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


ENVIRONMENTS = tuple(f"E{index}" for index in range(1, 7))
DEFAULT_TIERS = (4, 5, 6)


def parse_tiers(raw: str) -> tuple[int, ...]:
    try:
        tiers = tuple(int(value.strip()) for value in raw.split(",") if value.strip())
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "tiers must be a comma-separated subset of 1..6"
        ) from exc
    if (
        not tiers
        or len(tiers) != len(set(tiers))
        or any(tier not in range(1, 7) for tier in tiers)
    ):
        raise argparse.ArgumentTypeError(
            "tiers must be unique comma-separated values in 1..6"
        )
    return tuple(sorted(tiers))


def load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def one_match(root: Path, pattern: str) -> Path:
    matches = sorted(root.glob(pattern))
    if len(matches) != 1:
        raise ValueError(
            f"{root}: expected exactly one {pattern!r}, found {len(matches)}"
        )
    return matches[0]


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def validate_score(value: Any, *, field: str, task_id: str) -> None:
    if value is None:
        return
    require(
        isinstance(value, (int, float)) and float(value) == 1.0,
        f"{task_id}: {field} must be 1.0 when present, got {value!r}",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--expected-group-id", required=True)
    parser.add_argument("--expected-dataset", required=True)
    parser.add_argument("--expected-split", required=True)
    parser.add_argument("--expected-benchmark-revision", required=True)
    parser.add_argument("--expected-agenthub-ref", required=True)
    parser.add_argument("--expected-harbor-revision", required=True)
    parser.add_argument(
        "--expected-tiers",
        type=parse_tiers,
        default=DEFAULT_TIERS,
        help="comma-separated audited tiers; default: 4,5,6",
    )
    args = parser.parse_args()
    tiers = tuple(args.expected_tiers)
    expected_per_environment = 5 * len(tiers)
    expected_total = len(ENVIRONMENTS) * expected_per_environment

    jobs_root = args.export_root.resolve() / "jobs"
    job_dirs = sorted(path for path in jobs_root.iterdir() if path.is_dir())
    require(len(job_dirs) == 6, f"expected 6 exported jobs, found {len(job_dirs)}")

    rows: list[dict[str, Any]] = []
    environments: list[dict[str, Any]] = []
    seen_environments: set[str] = set()
    harbor_revisions: set[str] = set()

    for job_dir in job_dirs:
        job = load_object(job_dir / "job.json")
        episode = load_object(
            job_dir / "artifacts" / "output" / "dataset_episode.json"
        )
        audit_path = one_match(
            job_dir / "artifacts" / "output", "reference_solution_audit.json"
        )
        audit = load_object(audit_path)

        job_id = str(job.get("job_id") or job_dir.name)
        environment_id = str(job.get("instance_id") or "")
        require(environment_id in ENVIRONMENTS, f"{job_id}: invalid environment")
        require(
            environment_id not in seen_environments,
            f"duplicate environment {environment_id}",
        )
        seen_environments.add(environment_id)
        require(job.get("group_id") == args.expected_group_id, f"{job_id}: group mismatch")
        require(job.get("status") == "Succeeded", f"{job_id}: not Succeeded")
        require(job.get("attempt") == 0, f"{job_id}: unexpected retry attempt")
        require(
            job.get("agenthub_revision") == args.expected_agenthub_ref,
            f"{job_id}: Agent-Hub revision mismatch",
        )
        require(
            episode.get("environment_id") == environment_id,
            f"{job_id}: dataset episode environment mismatch",
        )
        require(
            episode.get("dataset") == args.expected_dataset,
            f"{job_id}: dataset mismatch",
        )
        require(
            episode.get("split") == args.expected_split,
            f"{job_id}: split mismatch",
        )
        require(
            episode.get("benchmark_revision") == args.expected_benchmark_revision,
            f"{job_id}: packaged benchmark revision mismatch",
        )
        require(
            audit.get("benchmark_revision") == args.expected_benchmark_revision,
            f"{job_id}: audit benchmark revision mismatch",
        )
        harbor = audit.get("harbor")
        require(isinstance(harbor, dict), f"{job_id}: missing Harbor metadata")
        harbor_revision = str(harbor.get("installed_git_commit") or "")
        require(
            harbor_revision == args.expected_harbor_revision,
            f"{job_id}: Harbor revision mismatch",
        )
        harbor_revisions.add(harbor_revision)
        execution = audit.get("execution")
        require(
            isinstance(execution, dict) and execution.get("agent") == "oracle",
            f"{job_id}: audit did not use Harbor oracle",
        )

        task_rows = audit.get("tasks")
        require(
            isinstance(task_rows, list) and len(task_rows) == expected_per_environment,
            f"{job_id}: expected {expected_per_environment} task rows",
        )
        expected_ids = {
            f"{environment_id}-LS{family}-T{tier}"
            for family in range(1, 6)
            for tier in tiers
        }
        actual_ids = {
            str(row.get("task_id"))
            for row in task_rows
            if isinstance(row, dict)
        }
        require(actual_ids == expected_ids, f"{job_id}: selected tier grid mismatch")

        for row in task_rows:
            require(isinstance(row, dict), f"{job_id}: non-object task row")
            task_id = str(row.get("task_id") or "")
            require(row.get("environment_id") == environment_id, f"{task_id}: env mismatch")
            require(row.get("strict_pass") is True, f"{task_id}: strict failure")
            require(row.get("normalized_score") == 1.0, f"{task_id}: score is not 1.0")
            require(row.get("trial_count") == 1, f"{task_id}: trial_count is not 1")
            require(row.get("result_present") is True, f"{task_id}: result missing")
            require(row.get("exception_info") is None, f"{task_id}: exception present")
            validate_score(row.get("outcome_passed"), field="outcome_passed", task_id=task_id)
            validate_score(row.get("process_passed"), field="process_passed", task_id=task_id)

        passed = sum(row.get("strict_pass") is True for row in task_rows)
        environments.append(
            {
                "environment_id": environment_id,
                "job_id": job_id,
                "attempt": job.get("attempt"),
                "passed": passed,
                "total": len(task_rows),
                "all_reference_solutions_pass": passed == len(task_rows),
            }
        )
        rows.extend(task_rows)

    require(seen_environments == set(ENVIRONMENTS), "six-environment coverage mismatch")
    require(
        len(rows) == expected_total,
        f"expected {expected_total} task rows, found {len(rows)}",
    )
    require(
        len({str(row.get("task_id")) for row in rows}) == expected_total,
        "task IDs are not unique",
    )

    rows.sort(key=lambda row: (str(row["environment_id"]), str(row["family_id"]), int(row["tier"])))
    environments.sort(key=lambda row: str(row["environment_id"]))
    by_tier = {
        str(tier): {
            "passed": sum(
                row.get("strict_pass") is True for row in rows if row.get("tier") == tier
            ),
            "total": sum(1 for row in rows if row.get("tier") == tier),
        }
        for tier in tiers
    }
    passed = sum(row.get("strict_pass") is True for row in rows)
    payload = {
        "schema_version": "1.0",
        "audit_type": "official_reference_solution_all_environments",
        "generated_at_utc": datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat(),
        "group_id": args.expected_group_id,
        "dataset": args.expected_dataset,
        "split": args.expected_split,
        "benchmark_revision": args.expected_benchmark_revision,
        "agenthub_revision": args.expected_agenthub_ref,
        "harbor_revisions": sorted(harbor_revisions),
        "tiers": list(tiers),
        "environments": environments,
        "summary": {
            "passed": passed,
            "total": expected_total,
            "unique_task_ids": expected_total,
            "all_reference_solutions_pass": passed == expected_total,
            "by_tier": by_tier,
        },
        "tasks": rows,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
