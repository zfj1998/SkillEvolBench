#!/usr/bin/env python3
"""Build a read-only evidence chain for same-session skill reflections.

This script intentionally reports *observational* transitions.  A source task and
the next different input can differ in difficulty, so fail->success (or
success->fail) is not a causal estimate of the skill patch's effect.  A matched
no-skill or retrieval-ablation run is required for that claim.

Examples:

    python scripts/audit_skill_utility.py /path/to/a/run
    python scripts/audit_skill_utility.py /path/to/group-export --format json

The input may be an exact SkillEvolBench run directory, an AP job export, or a
group-export directory.  Discovery is deliberately bounded to known layouts;
the script does not recursively walk arbitrary artifact trees.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

import yaml


TERMINAL_REFLECTION_STATUSES = {"completed", "noop", "rejected", "skipped"}
TRANSITIONS = (
    "fail_to_success",
    "fail_to_fail",
    "success_to_success",
    "success_to_fail",
)

QUALITY_RUBRIC = [
    {
        "dimension": "generality",
        "0": "task-specific answer or literal patch only",
        "1": "a reusable pattern, but narrowly scoped or underspecified",
        "2": "reusable decision rules, failure modes, and verification guidance",
    },
    {
        "dimension": "family_relevance",
        "0": "unrelated to the source family",
        "1": "partly related but misses the family's recurring mechanism",
        "2": "captures a mechanism that plausibly transfers within the family",
    },
    {
        "dimension": "not_answer_copy",
        "0": "copies source-task filenames, constants, tests, or final code as the recipe",
        "1": "mixes abstraction with avoidable source-specific details",
        "2": "method-level guidance without leaking the source task's literal answer",
    },
    {
        "dimension": "syntax_and_integrity",
        "0": "invalid candidate/frontmatter or missing required structure",
        "1": "parses, but references/assets or instructions are incomplete",
        "2": "valid candidate, valid skill frontmatter, and coherent referenced assets",
    },
    {
        "dimension": "downstream_reuse",
        "0": "not retrieved on a later different input",
        "1": "retrieved/injected, but no trajectory evidence that the agent used it",
        "2": "retrieved and listed in skills_actually_used on a later different input",
    },
]


def _json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        return []
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}: {exc}") from exc
            if isinstance(row, dict):
                rows.append(row)
    return rows


def _sha256_text(value: str | None) -> str | None:
    if not value:
        return None
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _run_git(library_dir: Path, *args: str) -> tuple[bool, str]:
    completed = subprocess.run(
        ["git", "-C", str(library_dir), *args],
        check=False,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    return completed.returncode == 0, completed.stdout.strip()


def _commit_exists(library_dir: Path, commit: str | None) -> bool | None:
    if not commit:
        return None
    ok, _ = _run_git(library_dir, "cat-file", "-e", f"{commit}^{{commit}}")
    return ok


def _is_run_dir(path: Path) -> bool:
    return (path / "stores" / "replay" / "records").is_dir()


def discover_run_dirs(inputs: Iterable[Path]) -> list[Path]:
    """Discover only known run layouts, avoiding an unbounded recursive walk."""

    discovered: set[Path] = set()
    patterns = (
        "artifacts/output/runs/*",
        "output/runs/*",
        "runs/*",
        "*/artifacts/output/runs/*",
        "*/output/runs/*",
        "jobs/*/artifacts/output/runs/*",
        "jobs/*/output/runs/*",
    )
    for raw in inputs:
        path = raw.expanduser().resolve()
        if _is_run_dir(path):
            discovered.add(path)
            continue
        for pattern in patterns:
            for candidate in path.glob(pattern):
                if _is_run_dir(candidate):
                    discovered.add(candidate.resolve())
    return sorted(discovered)


def _transition(source_passed: bool, next_passed: bool) -> str:
    if not source_passed and next_passed:
        return "fail_to_success"
    if not source_passed and not next_passed:
        return "fail_to_fail"
    if source_passed and next_passed:
        return "success_to_success"
    return "success_to_fail"


def _retrieved_skill_ids(record: dict[str, Any]) -> list[str]:
    retrieval = record.get("retrieval") or {}
    values = retrieval.get("skills") or retrieval.get("retrieved_skill_ids") or []
    result: list[str] = []
    for value in values:
        if isinstance(value, str):
            result.append(value)
        elif isinstance(value, dict) and isinstance(value.get("skill_id"), str):
            result.append(value["skill_id"])
    return result


def _query_text(record: dict[str, Any]) -> str | None:
    retrieval = record.get("retrieval") or {}
    value = retrieval.get("query_text")
    return value if isinstance(value, str) else None


def _validate_candidate(path: Path | None, rejection_reason: str) -> dict[str, Any]:
    present = bool(path and path.is_file())
    result: dict[str, Any] = {
        "path": str(path) if present else None,
        "expected_path": str(path) if path else None,
        "present": present,
        "sha256": None,
        "json_valid": None,
        "basic_skill_syntax_valid": None,
        "validation_errors": [],
        "summary": None,
        "operation_type": None,
        "upsert_paths": [],
    }
    if path is None or not path.is_file():
        if "invalid" in rejection_reason:
            result["basic_skill_syntax_valid"] = False
            result["validation_errors"].append(rejection_reason)
        return result

    result["sha256"] = _sha256_file(path)
    try:
        candidate = _json(path)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        result["json_valid"] = False
        result["basic_skill_syntax_valid"] = False
        result["validation_errors"].append(str(exc))
        return result

    result["json_valid"] = True
    result["summary"] = candidate.get("summary")
    result["operation_type"] = candidate.get("operation_type")
    upsert_files = candidate.get("upsert_files")
    if not isinstance(upsert_files, dict):
        result["basic_skill_syntax_valid"] = False
        result["validation_errors"].append("upsert_files is not an object")
        return result
    result["upsert_paths"] = sorted(str(key) for key in upsert_files)

    errors: list[str] = []
    skill_files = 0
    for raw_path, content in upsert_files.items():
        candidate_path = Path(str(raw_path))
        if candidate_path.is_absolute() or ".." in candidate_path.parts:
            errors.append(f"unsafe upsert path: {raw_path}")
        if not str(raw_path).endswith("/SKILL.md"):
            continue
        skill_files += 1
        if not isinstance(content, str) or not content.startswith("---\n"):
            errors.append(f"missing YAML frontmatter: {raw_path}")
            continue
        pieces = content.split("---", 2)
        if len(pieces) < 3:
            errors.append(f"unterminated YAML frontmatter: {raw_path}")
            continue
        try:
            frontmatter = yaml.safe_load(pieces[1])
        except yaml.YAMLError as exc:
            errors.append(f"invalid YAML frontmatter {raw_path}: {exc}")
            continue
        if not isinstance(frontmatter, dict):
            errors.append(f"frontmatter is not a mapping: {raw_path}")
            continue
        for key in ("name", "description"):
            if not isinstance(frontmatter.get(key), str) or not frontmatter[key].strip():
                errors.append(f"missing non-empty {key}: {raw_path}")

    operation = candidate.get("operation_type")
    if operation in {"create", "revise"} and skill_files == 0:
        errors.append(f"{operation} candidate has no */SKILL.md")
    result["validation_errors"] = errors
    result["basic_skill_syntax_valid"] = not errors
    return result


def _audit_dirs_by_task(run_dir: Path) -> dict[str, Path]:
    result: dict[str, Path] = {}
    for path in run_dir.glob(
        "harbor-job/*/*/self-reflection-audit/self_reflection_result.json"
    ):
        try:
            task_id = _json(path).get("task_id")
        except (OSError, ValueError, json.JSONDecodeError):
            continue
        if isinstance(task_id, str):
            result[task_id] = path.parent
    return result


def _stream_mentions_candidate(path: Path | None) -> bool | None:
    if path is None or not path.is_file():
        return None
    needle = "self_reflection_patch.json"
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        return any(needle in line for line in handle)


def _load_manifest_versions(
    run_dir: Path,
) -> tuple[dict[str, list[dict[str, Any]]], list[dict[str, Any]]]:
    by_patch: dict[str, list[dict[str, Any]]] = defaultdict(list)
    libraries: list[dict[str, Any]] = []
    for manifest_path in sorted(run_dir.glob("library/*/manifest.yaml")):
        library_dir = manifest_path.parent
        with manifest_path.open("r", encoding="utf-8") as handle:
            manifest = yaml.safe_load(handle) or {}
        version_rows: list[dict[str, Any]] = []
        for skill_id, skill in (manifest.get("skills") or {}).items():
            for version in skill.get("versions") or []:
                commit = version.get("git_commit")
                row = {
                    "library_dir": str(library_dir),
                    "skill_id": skill_id,
                    "skill_name": skill.get("name"),
                    "skill_status": skill.get("status"),
                    "current_version": skill.get("current_version"),
                    "version": version.get("version"),
                    "parent_version": version.get("parent_version"),
                    "patch_id": version.get("patch_id"),
                    "created_at_task": version.get("created_at_task"),
                    "skill_content_commit": commit,
                    "skill_content_commit_exists": _commit_exists(library_dir, commit),
                }
                version_rows.append(row)
                if isinstance(version.get("patch_id"), str):
                    by_patch[version["patch_id"]].append(row)

        head_ok, head = _run_git(library_dir, "rev-parse", "HEAD")
        log_ok, log_text = _run_git(
            library_dir,
            "log",
            "--reverse",
            "--format=%H%x09%P%x09%s",
            "--all",
        )
        history = []
        if log_ok:
            for line in log_text.splitlines():
                commit, parents, subject = (line.split("\t", 2) + ["", ""])[:3]
                history.append(
                    {"commit": commit, "parents": parents.split(), "subject": subject}
                )
        libraries.append(
            {
                "library_dir": str(library_dir),
                "manifest_path": str(manifest_path),
                "head": head if head_ok else None,
                "git_history": history,
                "versions": version_rows,
            }
        )
    return by_patch, libraries


def audit_run(run_dir: Path) -> dict[str, Any]:
    record_paths = sorted((run_dir / "stores" / "replay" / "records").glob("*.json"))
    records = [_json(path) for path in record_paths]
    records = [record for record in records if record.get("replay_mode", "primary") == "primary"]
    records.sort(key=lambda record: str(record.get("timestamp", "")))
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_family[str(record.get("family_id", ""))].append(record)

    patch_events = _jsonl(run_dir / "stores" / "events" / "patches.jsonl")
    lifecycle_events = _jsonl(run_dir / "stores" / "events" / "lifecycle.jsonl")
    audit_dirs = _audit_dirs_by_task(run_dir)
    versions_by_patch, libraries = _load_manifest_versions(run_dir)

    proposed_by_patch = {
        row["patch_id"]: row
        for row in patch_events
        if row.get("event_type") == "patch_proposed" and isinstance(row.get("patch_id"), str)
    }
    applied_by_patch = {
        row["patch_id"]: row
        for row in patch_events
        if row.get("event_type") == "patch_applied" and isinstance(row.get("patch_id"), str)
    }
    ended_by_task = {
        row["task_id"]: row
        for row in lifecycle_events
        if str(row.get("event_type", "")).startswith("trial_ended")
        and isinstance(row.get("task_id"), str)
    }

    chains: list[dict[str, Any]] = []
    warnings: list[str] = []
    for family_id, family_records in sorted(by_family.items()):
        for source_index, source in enumerate(family_records):
            reflection = source.get("reflection") or {}
            status = reflection.get("status")
            if status not in TERMINAL_REFLECTION_STATUSES:
                continue
            next_record = next(
                (
                    row
                    for row in family_records[source_index + 1 :]
                    if row.get("task_id") != source.get("task_id")
                ),
                None,
            )
            if next_record is None:
                continue

            task_id = str(source.get("task_id"))
            next_task_id = str(next_record.get("task_id"))
            audit_dir = audit_dirs.get(task_id)
            result_path = audit_dir / "self_reflection_result.json" if audit_dir else None
            candidate_path = audit_dir / "self_reflection_patch.json" if audit_dir else None
            stream_path = audit_dir / "opencode.reflection.jsonl" if audit_dir else None
            local_result = _json(result_path) if result_path and result_path.is_file() else {}
            reason = str(local_result.get("reason") or reflection.get("reason") or "")
            candidate = _validate_candidate(candidate_path, reason)
            patch_id = local_result.get("patch_id") or reflection.get("patch_id")
            proposed = proposed_by_patch.get(patch_id, {})
            applied = applied_by_patch.get(patch_id, {})
            versions = versions_by_patch.get(patch_id, [])
            patch_skill_ids = sorted(
                {
                    *[str(value) for value in proposed.get("target_skill_ids") or []],
                    *[
                        str(value)
                        for value in (applied.get("apply_result") or {}).get(
                            "affected_skill_ids", []
                        )
                    ],
                    *[str(row["skill_id"]) for row in versions],
                }
            )

            source_passed = bool((source.get("outcome") or {}).get("verifier_passed"))
            next_passed = bool((next_record.get("outcome") or {}).get("verifier_passed"))
            retrieved_next = _retrieved_skill_ids(next_record)
            used_next = [str(value) for value in next_record.get("skills_actually_used") or []]
            source_query_hash = _sha256_text(_query_text(source))
            next_query_hash = _sha256_text(_query_text(next_record))
            different_input_proven = bool(
                task_id != next_task_id
                and source_query_hash
                and next_query_hash
                and source_query_hash != next_query_hash
            )
            ended = ended_by_task.get(task_id, {})
            next_library_hash = next_record.get("library_hash_pre")
            post_patch_library_hash = ended.get("library_hash_after")
            apply_commit = (applied.get("apply_result") or {}).get("commit_hash")
            library_dir = Path(versions[0]["library_dir"]) if versions else None
            apply_commit_exists = (
                _commit_exists(library_dir, apply_commit) if library_dir else None
            )
            candidate_stream_mentioned = _stream_mentions_candidate(stream_path)
            if status == "rejected" and not candidate["present"] and candidate_stream_mentioned:
                warnings.append(
                    f"{task_id}: rejected raw candidate is evidenced only in the reflection stream; "
                    "no normalized self_reflection_patch.json was preserved"
                )

            chains.append(
                {
                    "run_dir": str(run_dir),
                    "family_id": family_id,
                    "source_task_id": task_id,
                    "source_task_role": source.get("task_role"),
                    "source_verifier_passed": source_passed,
                    "source_reward": (source.get("outcome") or {}).get("reward"),
                    "reflection_status": status,
                    "reflection_mode": local_result.get("mode") or reflection.get("mode"),
                    "reflection_reason": reason,
                    "same_session_verified": bool(
                        local_result.get("same_session_verified", reflection.get("same_session_verified"))
                    ),
                    "reflection_result_path": str(result_path) if result_path and result_path.is_file() else None,
                    "reflection_stream_path": str(stream_path) if stream_path and stream_path.is_file() else None,
                    "candidate_stream_mentions_patch_file": candidate_stream_mentioned,
                    "candidate": candidate,
                    "patch_id": patch_id,
                    "patch_proposed": bool(proposed),
                    "patch_applied": bool(applied),
                    "patch_operation_type": proposed.get("operation_type"),
                    "patch_summary": proposed.get("summary") or candidate.get("summary"),
                    "patch_skill_ids": patch_skill_ids,
                    "patch_apply_commit": apply_commit,
                    "patch_apply_commit_exists": apply_commit_exists,
                    "skill_versions": versions,
                    "skill_version_recorded": bool(versions),
                    "post_patch_library_hash": post_patch_library_hash,
                    "next_task_id": next_task_id,
                    "next_task_role": next_record.get("task_role"),
                    "source_input_sha256": source_query_hash,
                    "next_input_sha256": next_query_hash,
                    "different_input_proven": different_input_proven,
                    "next_library_hash_pre": next_library_hash,
                    "patch_state_visible_to_next_task": bool(
                        applied
                        and post_patch_library_hash
                        and next_library_hash
                        and post_patch_library_hash == next_library_hash
                    ),
                    "next_retrieved_skill_ids": retrieved_next,
                    "next_skills_actually_used": used_next,
                    "patch_skill_retrieved_next": bool(set(patch_skill_ids) & set(retrieved_next)),
                    "patch_skill_used_next": bool(set(patch_skill_ids) & set(used_next)),
                    "next_verifier_passed": next_passed,
                    "next_reward": (next_record.get("outcome") or {}).get("reward"),
                    "transition": _transition(source_passed, next_passed),
                    "interpretation": "observational_noncausal",
                }
            )

    run_id = run_dir.name
    config_path = run_dir / "config.json"
    if config_path.is_file():
        run_id = str(_json(config_path).get("run_id") or run_id)
    return {
        "run_id": run_id,
        "run_dir": str(run_dir),
        "n_primary_records": len(records),
        "chains": chains,
        "libraries": libraries,
        "warnings": sorted(set(warnings)),
    }


def _review_queue(chains: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    high_priority: list[dict[str, Any]] = []
    by_family: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for chain in chains:
        by_family[chain["family_id"]].append(chain)
        if (
            chain["transition"] != "success_to_success"
            or chain["reflection_status"] != "completed"
            or not chain["patch_applied"]
            or (chain["patch_skill_ids"] and not chain["patch_skill_retrieved_next"])
        ):
            high_priority.append(chain)

    selected_ids = {(row["run_dir"], row["source_task_id"]) for row in high_priority}
    stratified: list[dict[str, Any]] = []
    for family_id in sorted(by_family):
        candidate = next(
            (
                row
                for row in by_family[family_id]
                if row["patch_applied"]
                and (row["run_dir"], row["source_task_id"]) not in selected_ids
            ),
            None,
        )
        if candidate:
            stratified.append(candidate)

    def compact(row: dict[str, Any]) -> dict[str, Any]:
        candidate = row["candidate"]
        return {
            "run_id": Path(row["run_dir"]).name,
            "family_id": row["family_id"],
            "source_task_id": row["source_task_id"],
            "reflection_status": row["reflection_status"],
            "transition": row["transition"],
            "candidate_path": candidate["path"],
            "reflection_stream_path": row["reflection_stream_path"],
            "patch_skill_ids": row["patch_skill_ids"],
            "next_task_id": row["next_task_id"],
        }

    return {
        "high_priority": [compact(row) for row in high_priority],
        "one_additional_applied_candidate_per_family": [
            compact(row) for row in stratified
        ],
    }


def aggregate(runs: list[dict[str, Any]]) -> dict[str, Any]:
    chains = [chain for run in runs for chain in run["chains"]]
    transition_counts = Counter(chain["transition"] for chain in chains)
    status_counts = Counter(chain["reflection_status"] for chain in chains)
    applied = [chain for chain in chains if chain["patch_applied"]]
    applied_retrieved = [chain for chain in applied if chain["patch_skill_retrieved_next"]]
    applied_used = [chain for chain in applied if chain["patch_skill_used_next"]]
    return {
        "n_runs": len(runs),
        "n_primary_records": sum(run["n_primary_records"] for run in runs),
        "n_reflection_to_next_input_chains": len(chains),
        "reflection_status_counts": dict(sorted(status_counts.items())),
        "transition_counts": {name: transition_counts.get(name, 0) for name in TRANSITIONS},
        "n_candidates_preserved": sum(chain["candidate"]["present"] for chain in chains),
        "n_patches_applied": len(applied),
        "n_applied_patches_with_version_record": sum(
            chain["skill_version_recorded"] for chain in applied
        ),
        "n_applied_patches_visible_to_next_task": sum(
            chain["patch_state_visible_to_next_task"] for chain in applied
        ),
        "n_applied_patches_retrieved_on_next_input": len(applied_retrieved),
        "n_applied_patches_used_on_next_input": len(applied_used),
        "applied_patch_transition_counts": {
            name: sum(chain["transition"] == name for chain in applied)
            for name in TRANSITIONS
        },
        "applied_and_retrieved_transition_counts": {
            name: sum(chain["transition"] == name for chain in applied_retrieved)
            for name in TRANSITIONS
        },
        "review_queue": _review_queue(chains),
    }


def build_report(run_dirs: list[Path]) -> dict[str, Any]:
    runs = [audit_run(path) for path in run_dirs]
    return {
        "schema_version": 1,
        "claim_boundary": (
            "All transition and reuse results are observational, not causal. "
            "The next task is a different input and may differ in difficulty. "
            "Estimate skill effect with a matched no-skill or retrieval-ablation control."
        ),
        "content_quality_rubric": QUALITY_RUBRIC,
        "aggregate": aggregate(runs),
        "runs": runs,
    }


def _cell(value: Any) -> str:
    if isinstance(value, bool):
        return "yes" if value else "no"
    if value is None:
        return "-"
    if isinstance(value, list):
        value = ", ".join(str(item) for item in value) or "-"
    return str(value).replace("|", "\\|").replace("\n", " ")


def render_markdown(report: dict[str, Any]) -> str:
    aggregate_data = report["aggregate"]
    lines = [
        "# Skill utility evidence audit",
        "",
        f"> {report['claim_boundary']}",
        "",
        "## Aggregate",
        "",
        f"- Runs: {aggregate_data['n_runs']}",
        f"- Primary records: {aggregate_data['n_primary_records']}",
        f"- Reflection -> next different input chains: {aggregate_data['n_reflection_to_next_input_chains']}",
        f"- Applied patches: {aggregate_data['n_patches_applied']}",
        f"- Applied + versioned: {aggregate_data['n_applied_patches_with_version_record']}",
        f"- Applied + visible at next task: {aggregate_data['n_applied_patches_visible_to_next_task']}",
        f"- Applied + retrieved next: {aggregate_data['n_applied_patches_retrieved_on_next_input']}",
        f"- Applied + actually used next: {aggregate_data['n_applied_patches_used_on_next_input']}",
        "",
        "| transition | all reflections | applied patches | applied and retrieved |",
        "| --- | ---: | ---: | ---: |",
    ]
    for transition in TRANSITIONS:
        lines.append(
            "| "
            + " | ".join(
                [
                    transition,
                    str(aggregate_data["transition_counts"][transition]),
                    str(aggregate_data["applied_patch_transition_counts"][transition]),
                    str(aggregate_data["applied_and_retrieved_transition_counts"][transition]),
                ]
            )
            + " |"
        )

    lines.extend(
        [
            "",
            "## Evidence chains",
            "",
            "| source | status | applied/versioned | next different input | patch skill retrieved/used | verifier transition | reward |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for run in report["runs"]:
        for chain in run["chains"]:
            lines.append(
                "| "
                + " | ".join(
                    _cell(value)
                    for value in (
                        chain["source_task_id"],
                        chain["reflection_status"],
                        f"{chain['patch_applied']}/{chain['skill_version_recorded']}",
                        f"{chain['next_task_id']} ({chain['different_input_proven']})",
                        f"{chain['patch_skill_retrieved_next']}/{chain['patch_skill_used_next']}",
                        chain["transition"],
                        f"{chain['source_reward']} -> {chain['next_reward']}",
                    )
                )
                + " |"
            )

    lines.extend(["", "## Skill versions and Git evidence", ""])
    for run in report["runs"]:
        lines.append(f"### {_cell(run['run_id'])}")
        lines.append("")
        for library in run["libraries"]:
            lines.append(f"- Library: `{library['library_dir']}`")
            lines.append(f"- HEAD: `{library['head']}`")
            for version in library["versions"]:
                lines.append(
                    "- "
                    f"{version['skill_id']} v{version['version']} from "
                    f"{version['created_at_task']}: `{version['skill_content_commit']}` "
                    f"(commit exists: {version['skill_content_commit_exists']})"
                )
        for warning in run["warnings"]:
            lines.append(f"- Audit warning: {warning}")
        lines.append("")

    lines.extend(
        [
            "## Manual content-quality rubric",
            "",
            "Score each dimension 0-2. A high score is evidence of plausible reusable content, not proof of causal task improvement.",
            "",
            "| dimension | 0 | 1 | 2 |",
            "| --- | --- | --- | --- |",
        ]
    )
    for row in report["content_quality_rubric"]:
        lines.append(
            "| " + " | ".join(_cell(row[key]) for key in ("dimension", "0", "1", "2")) + " |"
        )

    queue = aggregate_data["review_queue"]
    lines.extend(
        [
            "",
            "## Manual review queue",
            "",
            "Review every rejected/no-op, fail->success, success->fail, applied-but-not-retrieved case, then one additional applied candidate per family.",
            "",
        ]
    )
    for label, rows in queue.items():
        lines.append(f"### {label}")
        lines.append("")
        for row in rows:
            evidence_path = row["candidate_path"] or row["reflection_stream_path"] or "missing"
            lines.append(
                f"- {row['source_task_id']} -> {row['next_task_id']} "
                f"({row['reflection_status']}, {row['transition']}): `{evidence_path}`"
            )
        if not rows:
            lines.append("- None")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "paths",
        nargs="+",
        type=Path,
        help="Exact run dir, AP job export, or AP group export",
    )
    parser.add_argument("--format", choices=("markdown", "json"), default="markdown")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_dirs = discover_run_dirs(args.paths)
    if not run_dirs:
        searched = ", ".join(str(path) for path in args.paths)
        raise SystemExit(f"no SkillEvolBench run directories found under: {searched}")
    report = build_report(run_dirs)
    if args.format == "json":
        print(json.dumps(report, indent=2, sort_keys=True))
    else:
        print(render_markdown(report), end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
