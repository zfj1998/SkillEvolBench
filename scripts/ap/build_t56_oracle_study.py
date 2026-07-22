#!/usr/bin/env python3
"""Build a reproducible evidence table for the T4-T6 oracle study.

The collector intentionally separates AP/job completion, strict verifier pass,
outcome pass, and process pass.  This prevents a platform-level success or a
process-only verifier failure from being mistaken for task capability.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml


TASK_ID_RE = re.compile(r"^(E[1-6])-LS([1-5])-T([1-6])$")


def load_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        value = json.load(handle)
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def load_optional_json(path: Path | None) -> Any:
    if path is None or not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        digest.update(path.relative_to(root).as_posix().encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def projected_skill_digest(skill_md: bytes) -> str:
    """Hash the active-library projection created by ``inject_curated``.

    Curated benchmark folders also contain ``meta.yaml``, but the runtime
    library intentionally copies only ``SKILL.md``.  Keep this byte-level
    helper aligned with the oracle-view audit in ``harbor_ext/hooks.py``.
    """
    digest = hashlib.sha256()
    digest.update(b"SKILL.md")
    digest.update(b"\0")
    digest.update(skill_md)
    digest.update(b"\0")
    return digest.hexdigest()


def sanitized_skill_matches_runtime_audit(
    *,
    skill_dir: Path,
    audit_sha256: str,
    slug: str,
    skills_root: Path,
    output_root: Path,
) -> bool:
    """Verify a redacted export against runtime hashes and canonical bytes.

    AP sanitization runs *after* the episode and may redact placeholder bearer
    tokens inside a curated SKILL.md.  The runtime oracle audit therefore
    hashes the bytes the model saw, while the downloaded tree contains the
    redacted bytes.  Accept that difference only when all three links agree:
    canonical curated bytes -> audit tree hash, canonical file hash ->
    manifest runtime hash, and delivered bytes -> manifest delivered hash.
    """
    files = sorted(
        path.relative_to(skill_dir).as_posix()
        for path in skill_dir.rglob("*")
        if path.is_file()
    )
    if files != ["SKILL.md"]:
        return False
    canonical_path = skills_root / slug / "SKILL.md"
    if not canonical_path.is_file():
        return False
    canonical = canonical_path.read_bytes()
    if projected_skill_digest(canonical) != audit_sha256:
        return False

    manifest_path = output_root / "sanitization_manifest.json"
    try:
        manifest = load_json(manifest_path)
    except (OSError, ValueError, json.JSONDecodeError):
        return False
    changed = {
        str(item.get("path")): item
        for item in manifest.get("changed_files") or []
        if isinstance(item, dict) and item.get("path")
    }
    delivered_path = skill_dir / "SKILL.md"
    try:
        relative = delivered_path.relative_to(output_root).as_posix()
    except ValueError:
        return False
    entry = changed.get(relative)
    if not isinstance(entry, dict):
        return False
    delivered = delivered_path.read_bytes()
    return (
        entry.get("runtime_sha256") == hashlib.sha256(canonical).hexdigest()
        and entry.get("runtime_size") == len(canonical)
        and entry.get("delivered_sha256") == hashlib.sha256(delivered).hexdigest()
        and entry.get("delivered_size") == len(delivered)
    )


def oracle_evidence(
    run_dir: Path,
    task_id: str,
    spec: dict[str, Any],
    oracle_enabled: bool,
    raw_root: Path,
    skills_root: Path | None = None,
) -> dict[str, Any]:
    if not oracle_enabled:
        return {
            "oracle_injection_exact": None,
            "oracle_audit_path": None,
            "oracle_skill_ids": [],
            "expected_oracle_skill_ids": [],
            "oracle_injection_errors": [],
        }
    expected = (
        list(spec.get("required_skills") or [])
        if int(spec.get("task_index", 0)) == 6
        else [str(spec.get("primary_skill"))]
    )
    audit_path = run_dir / "oracle-skill-views" / f"{task_id}.audit.json"
    view_dir = run_dir / "oracle-skill-views" / task_id
    errors: list[str] = []
    audit: dict[str, Any] = {}
    if not audit_path.exists():
        errors.append("missing oracle audit")
    else:
        try:
            audit = load_json(audit_path)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            errors.append(f"invalid oracle audit: {exc}")
    actual = list(audit.get("oracle_skill_ids") or [])
    if actual != expected:
        errors.append(f"oracle IDs differ: actual={actual!r} expected={expected!r}")
    expected_slugs = sorted(skill.split(".", 1)[-1] for skill in expected)
    visible_slugs = (
        sorted(path.name for path in view_dir.iterdir() if path.is_dir())
        if view_dir.is_dir() else []
    )
    if visible_slugs != expected_slugs:
        errors.append(f"visible skill dirs differ: actual={visible_slugs!r} expected={expected_slugs!r}")
    content_verification: dict[str, str] = {}
    for skill in audit.get("skills") or []:
        if not isinstance(skill, dict):
            errors.append("non-object oracle skill audit entry")
            continue
        skill_dir = view_dir / str(skill.get("slug"))
        if not skill_dir.is_dir():
            errors.append(f"missing oracle skill dir: {skill.get('slug')}")
        elif tree_digest(skill_dir) == skill.get("sha256"):
            content_verification[str(skill.get("slug"))] = "delivered_tree"
        elif skills_root is not None and sanitized_skill_matches_runtime_audit(
            skill_dir=skill_dir,
            audit_sha256=str(skill.get("sha256") or ""),
            slug=str(skill.get("slug") or ""),
            skills_root=skills_root,
            output_root=run_dir.parents[1],
        ):
            content_verification[str(skill.get("slug"))] = (
                "runtime_hash_via_sanitization_manifest"
            )
        else:
            errors.append(f"oracle content hash mismatch: {skill.get('slug')}")
    return {
        "oracle_injection_exact": not errors,
        "oracle_audit_path": (
            relative_or_absolute(audit_path, raw_root) if audit_path.exists() else None
        ),
        "oracle_skill_ids": actual,
        "expected_oracle_skill_ids": expected,
        "oracle_injection_errors": errors,
        "oracle_content_verification": content_verification,
    }


def curated_all_evidence(
    run_dir: Path,
    environment_id: str,
    specs: dict[str, dict[str, Any]],
    skills_root: Path,
) -> dict[str, Any]:
    expected_by_family = {
        str(spec.get("family_id")): str(spec.get("latent_skill_id"))
        for spec in specs.values()
        if spec.get("environment_id") == environment_id
        and spec.get("family_id")
        and spec.get("latent_skill_id")
    }
    expected_slugs = sorted(
        skill_id.split(".", 1)[-1] for skill_id in expected_by_family.values()
    )
    active_dir = run_dir / "library" / environment_id / "active"
    visible_slugs = (
        sorted(
            path.name
            for path in active_dir.iterdir()
            if path.is_dir()
            and not path.is_symlink()
            and (path / "SKILL.md").is_file()
        )
        if active_dir.is_dir()
        else []
    )
    errors: list[str] = []
    if len(expected_by_family) != 5:
        errors.append(f"expected five families, got {len(expected_by_family)}")
    if visible_slugs != expected_slugs:
        errors.append(
            f"visible skill dirs differ: actual={visible_slugs!r} "
            f"expected={expected_slugs!r}"
        )
    for slug in expected_slugs:
        active_skill = active_dir / slug / "SKILL.md"
        curated_skill = skills_root / slug / "SKILL.md"
        if not active_skill.is_file():
            errors.append(f"missing active curated skill: {slug}")
        elif not curated_skill.is_file():
            errors.append(f"missing source curated skill: {slug}")
        elif active_skill.read_bytes() != curated_skill.read_bytes():
            errors.append(f"curated content mismatch: {slug}")
    if not (active_dir.parent / ".frozen").is_file():
        errors.append("curated environment library is not frozen")
    return {
        "curated_all_library_complete": not errors,
        "curated_all_visible_slugs": visible_slugs,
        "curated_all_expected_slugs": expected_slugs,
        "curated_all_library_errors": errors,
    }


def load_task_specs(tasks_root: Path) -> dict[str, dict[str, Any]]:
    specs: dict[str, dict[str, Any]] = {}
    for path in sorted(tasks_root.glob("*/task-spec.yaml")):
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict) or not value.get("task_id"):
            raise ValueError(f"invalid task spec: {path}")
        value["_path"] = str(path.resolve())
        specs[str(value["task_id"])] = value
    return specs


def load_inventory(path: Path) -> dict[str, dict[str, Any]]:
    if not path.exists():
        return {}
    inventory = load_json(path)
    return {
        str(row["job_id"]): row
        for row in inventory.get("jobs", [])
        if isinstance(row, dict) and row.get("job_id")
    }


def markdown_description(text: str) -> str:
    if not text.startswith("---\n"):
        return ""
    end = text.find("\n---\n", 4)
    if end < 0:
        return ""
    frontmatter = yaml.safe_load(text[4:end]) or {}
    return str(frontmatter.get("description") or "") if isinstance(frontmatter, dict) else ""


def markdown_headings(text: str) -> list[str]:
    return [
        line.lstrip("#").strip()
        for line in text.splitlines()
        if line.startswith("#") and line.lstrip("#").startswith(" ")
    ]


def word_set(text: str) -> set[str]:
    return set(re.findall(r"[a-zA-Z][a-zA-Z0-9_-]{2,}", text.lower()))


def jaccard(left: set[str], right: set[str]) -> float | None:
    union = left | right
    return len(left & right) / len(union) if union else None


def enrich_failed_tests(
    failed_tests: list[Any], spec: dict[str, Any]
) -> list[dict[str, Any]]:
    task_root = Path(str(spec.get("_path", ""))).parent
    test_files = sorted((task_root / "tests").glob("**/*.py"))
    enriched: list[dict[str, Any]] = []
    for raw in failed_tests:
        if not isinstance(raw, dict):
            continue
        item = dict(raw)
        method = str(item.get("name") or "").split(".")[-1]
        needle = re.compile(rf"^\s*(?:async\s+)?def\s+{re.escape(method)}\s*\(")
        for path in test_files:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for line_number, line in enumerate(lines, 1):
                if needle.search(line):
                    item["test_source_path"] = str(path.resolve())
                    item["test_source_line"] = line_number
                    break
            if item.get("test_source_path"):
                break
            for line_number, line in enumerate(lines, 1):
                if method and method in line:
                    item["test_source_path"] = str(path.resolve())
                    item["test_source_line"] = line_number
                    break
            if item.get("test_source_path"):
                break
        enriched.append(item)
    return enriched


def model_family(label: str, model_name: str) -> str:
    value = f"{label} {model_name}".lower()
    if "qwen" in value:
        return "qwen3.7-max"
    if "fable" in value or "3.8-maxp" in value:
        return "sig-fable"
    return model_name or "unknown"


def condition_name(config: dict[str, Any]) -> str:
    baseline = config.get("baseline") or {}
    name = str(baseline.get("name") or "unknown")
    oracle_view = bool(config.get("oracle_skill_view"))
    if oracle_view and name == "curated_static":
        return "exact_oracle"
    if name == "curated_static":
        return "curated_all"
    if name == "no_skill":
        return "no_skill"
    if name.startswith("selfgen"):
        return "self_generated"
    return name


def classify(outcome: dict[str, Any]) -> str:
    strict = outcome.get("verifier_passed")
    result = outcome.get("outcome_passed")
    process = outcome.get("process_passed")
    if strict is True:
        return "strict_pass"
    if result is True and process is False:
        return "process_only_failure"
    if result is False and process is True:
        return "outcome_only_failure"
    if result is False and process is False:
        return "outcome_and_process_failure"
    return "unknown"


def skill_ids(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    result: list[str] = []
    for item in value:
        if isinstance(item, str):
            result.append(item)
        elif isinstance(item, dict) and item.get("skill_id"):
            result.append(str(item["skill_id"]))
    return result


def relative_or_absolute(path: Path, root: Path) -> str:
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path.resolve())


def iter_run_dirs(raw_root: Path) -> Iterable[Path]:
    # The watcher exports a stable four-level layout.  Avoid an expensive
    # recursive filesystem walk over large task/container artifacts.
    yield from sorted(raw_root.glob("*/ap-*/artifacts/output/runs/*"))


def mark_selected_runs(
    runs: list[dict[str, Any]],
    rows: list[dict[str, Any]],
    skill_rows: list[dict[str, Any]],
) -> set[tuple[str, str]]:
    """Mark one non-blended episode per model/condition/environment."""
    task_counts = Counter((row["job_id"], row["run_id"]) for row in rows)
    grouped_runs: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for run in runs:
        grouped_runs[(run["model"], run["condition"], run["environment_id"])].append(run)
    selected_keys: set[tuple[str, str]] = set()
    for candidates in grouped_runs.values():
        selected = max(
            candidates,
            key=lambda run: (
                task_counts[(run["job_id"], run["run_id"])],
                run["ap_status"] == "Succeeded",
                str(run.get("ap_updated_at") or run.get("ap_created_at") or ""),
            ),
        )
        selected_keys.add((selected["job_id"], selected["run_id"]))
    for collection in (runs, rows, skill_rows):
        for item in collection:
            item["selected_run"] = (item["job_id"], item["run_id"]) in selected_keys
    for run in runs:
        run["selected_t56_record_count"] = task_counts[(run["job_id"], run["run_id"])]
        run["selection_rule"] = "max_t56_coverage_then_ap_success_then_latest"
    return selected_keys


def collect(
    raw_root: Path,
    tasks_root: Path,
    skills_root: Path,
    inventory_path: Path,
) -> dict[str, Any]:
    specs = load_task_specs(tasks_root)
    inventory = load_inventory(inventory_path)
    rows: list[dict[str, Any]] = []
    learning_rows: list[dict[str, Any]] = []
    runs: list[dict[str, Any]] = []
    skill_rows: list[dict[str, Any]] = []
    expected_skill_by_family = {
        str(spec.get("family_id")): str(spec.get("latent_skill_id"))
        for spec in specs.values()
        if spec.get("family_id") and spec.get("latent_skill_id")
    }

    for run_dir in iter_run_dirs(raw_root):
        config_path = run_dir / "config.json"
        records_dir = run_dir / "stores" / "replay" / "records"
        if not config_path.exists() or not records_dir.is_dir():
            continue
        config = load_json(config_path)
        job_dir = run_dir.parents[3]
        job_id = job_dir.name
        export_label = job_dir.parent.name
        job = inventory.get(job_id, {})
        baseline = config.get("baseline") or {}
        condition = condition_name(config)
        model = model_family(export_label, str(baseline.get("model_name") or ""))
        run_row = {
            "run_id": config.get("run_id", run_dir.name),
            "job_id": job_id,
            "job_label": job.get("label", export_label),
            "ap_status": job.get("status", "unknown"),
            "ap_error_code": job.get("error_code"),
            "ap_created_at": job.get("created_at"),
            "ap_updated_at": job.get("updated_at"),
            "environment_id": config.get("environment_id"),
            "model": model,
            "model_name": baseline.get("model_name"),
            "baseline": baseline.get("name"),
            "condition": condition,
            "evaluation_only_t4_t6": bool(config.get("evaluation_only_t4_t6")),
            "oracle_skill_view": bool(config.get("oracle_skill_view")),
            "run_path": relative_or_absolute(run_dir, raw_root),
        }
        runs.append(run_row)

        active_dir = run_dir / "library" / str(config.get("environment_id")) / "active"
        curated_all = (
            curated_all_evidence(
                run_dir,
                str(config.get("environment_id") or ""),
                specs,
                skills_root,
            )
            if condition == "curated_all"
            else {
                "curated_all_library_complete": None,
                "curated_all_visible_slugs": [],
                "curated_all_expected_slugs": [],
                "curated_all_library_errors": [],
            }
        )
        if active_dir.is_dir():
            manifest_path = active_dir.parent / "manifest.yaml"
            manifest = (
                yaml.safe_load(manifest_path.read_text(encoding="utf-8")) or {}
                if manifest_path.exists()
                else {}
            )
            manifest_skills = (
                manifest.get("skills", {}) if isinstance(manifest, dict) else {}
            )
            for generated_path in sorted(active_dir.glob("*/SKILL.md")):
                slug = generated_path.parent.name
                entry: dict[str, Any] = {}
                if isinstance(manifest_skills, dict):
                    for candidate in manifest_skills.values():
                        if not isinstance(candidate, dict):
                            continue
                        candidate_slug = str(
                            candidate.get("name")
                            or str(candidate.get("skill_id") or "").split(".", 1)[-1]
                        )
                        if candidate_slug == slug:
                            entry = candidate
                            break
                skill_id = entry.get("skill_id")
                family_id = entry.get("family_id")
                expected_skill_id = expected_skill_by_family.get(str(family_id))
                expected_slug = (
                    expected_skill_id.split(".", 1)[-1]
                    if expected_skill_id
                    else slug
                )
                curated_path = skills_root / expected_slug / "SKILL.md"
                generated_text = generated_path.read_text(encoding="utf-8")
                curated_text = (
                    curated_path.read_text(encoding="utf-8")
                    if curated_path.exists()
                    else ""
                )
                generated_words = word_set(generated_text)
                curated_words = word_set(curated_text)
                generated_headings = markdown_headings(generated_text)
                curated_headings = markdown_headings(curated_text)
                skill_rows.append({
                    **run_row,
                    "skill_id": skill_id,
                    "family_id": family_id,
                    "skill_slug": slug,
                    "expected_oracle_skill_id": expected_skill_id,
                    "expected_oracle_skill_slug": expected_slug,
                    "renamed_from_oracle": bool(expected_skill_id and slug != expected_slug),
                    "current_version": entry.get("current_version"),
                    "created_at_task": entry.get("created_at_task"),
                    "last_revised_at_task": entry.get("last_revised_at_task"),
                    "version_summaries": [
                        {
                            "version": version.get("version"),
                            "created_at_task": version.get("created_at_task"),
                            "summary": version.get("summary"),
                        }
                        for version in entry.get("versions", [])
                        if isinstance(version, dict)
                    ],
                    "generated_path": relative_or_absolute(generated_path, raw_root),
                    "curated_path": str(curated_path.resolve()),
                    "generated_sha256": hashlib.sha256(generated_text.encode()).hexdigest(),
                    "curated_sha256": hashlib.sha256(curated_text.encode()).hexdigest(),
                    "exact_equal": generated_text == curated_text,
                    "generated_chars": len(generated_text),
                    "curated_chars": len(curated_text),
                    "generated_lines": len(generated_text.splitlines()),
                    "curated_lines": len(curated_text.splitlines()),
                    "generated_description": markdown_description(generated_text),
                    "curated_description": markdown_description(curated_text),
                    "generated_headings": generated_headings,
                    "curated_headings": curated_headings,
                    "word_jaccard": jaccard(generated_words, curated_words),
                    "heading_jaccard": jaccard(
                        set(map(str.lower, generated_headings)),
                        set(map(str.lower, curated_headings)),
                    ),
                    "generated_text": generated_text,
                    "curated_text": curated_text,
                })

        for record_path in sorted(records_dir.glob("E*-LS*-T[4-6].json")):
            record = load_json(record_path)
            task_id = str(record.get("task_id") or record_path.stem)
            match = TASK_ID_RE.match(task_id)
            if not match:
                continue
            spec = specs.get(task_id, {})
            outcome = record.get("outcome") or {}
            failed_tests = enrich_failed_tests(outcome.get("failed_tests") or [], spec)
            dimensions = outcome.get("rubric_dimensions") or []
            dimension_rows = {
                str(item.get("name")): {
                    "matched": item.get("tests_matched"),
                    "passed": item.get("tests_passed"),
                    "ratio": item.get("ratio"),
                    "score": item.get("score"),
                }
                for item in dimensions
                if isinstance(item, dict) and item.get("name")
            }
            retrieval = record.get("retrieval") or {}
            oracle = oracle_evidence(
                run_dir,
                task_id,
                spec,
                bool(config.get("oracle_skill_view")),
                raw_root,
                skills_root,
            )
            trial_candidates = sorted(
                (run_dir / "harbor-job" / str(config.get("run_id", run_dir.name))).glob(
                    f"{task_id}__*"
                )
            )
            trial_dir = trial_candidates[0] if len(trial_candidates) == 1 else None
            artifact_task_dir = trial_dir / "artifacts/root/task" if trial_dir else None
            local_trajectory = trial_dir / "agent/trajectory.json" if trial_dir else None
            row = {
                **run_row,
                **oracle,
                **curated_all,
                "task_id": task_id,
                "family_id": record.get("family_id") or spec.get("family_id"),
                "family_index": int(match.group(2)),
                "tier": int(match.group(3)),
                "task_slug": spec.get("task_slug"),
                "task_role": record.get("task_role") or spec.get("role"),
                "strict_pass": outcome.get("verifier_passed"),
                "reward": outcome.get("reward"),
                "normalized_score": outcome.get("normalized_score"),
                "outcome_pass": outcome.get("outcome_passed"),
                "process_pass": outcome.get("process_passed"),
                "classification": classify(outcome),
                "failed_tests": failed_tests,
                "failed_outcome_tests": [
                    item for item in failed_tests
                    if isinstance(item, dict) and item.get("group") == "outcome"
                ],
                "failed_process_tests": [
                    item for item in failed_tests
                    if isinstance(item, dict) and item.get("group") == "process"
                ],
                "rubric_dimensions": dimension_rows,
                "retrieved_skill_ids": skill_ids(retrieval.get("skills")),
                "skills_actually_used": skill_ids(record.get("skills_actually_used")),
                "no_skill_empty": (
                    not skill_ids(retrieval.get("skills"))
                    and not skill_ids(record.get("skills_actually_used"))
                    if condition == "no_skill"
                    else None
                ),
                "primary_skill": spec.get("primary_skill"),
                "required_skills": spec.get("required_skills") or [],
                "composition_type": spec.get("composition_type"),
                "trajectory_path": outcome.get("trajectory_path"),
                "local_trial_path": (
                    relative_or_absolute(trial_dir, raw_root) if trial_dir else None
                ),
                "local_artifact_task_path": (
                    relative_or_absolute(artifact_task_dir, raw_root)
                    if artifact_task_dir and artifact_task_dir.is_dir()
                    else None
                ),
                "local_trajectory_path": (
                    relative_or_absolute(local_trajectory, raw_root)
                    if local_trajectory and local_trajectory.exists()
                    else None
                ),
                "record_path": relative_or_absolute(record_path, raw_root),
                "task_spec_path": spec.get("_path"),
            }
            rows.append(row)

        for record_path in sorted(records_dir.glob("E*-LS*-T[1-3].json")):
            record = load_json(record_path)
            task_id = str(record.get("task_id") or record_path.stem)
            match = TASK_ID_RE.match(task_id)
            if not match:
                continue
            spec = specs.get(task_id, {})
            outcome = record.get("outcome") or {}
            reflection = record.get("reflection") or {}
            failed_tests = enrich_failed_tests(outcome.get("failed_tests") or [], spec)
            trial_candidates = sorted(
                (run_dir / "harbor-job" / str(config.get("run_id", run_dir.name))).glob(
                    f"{task_id}__*"
                )
            )
            trial_dir = trial_candidates[0] if len(trial_candidates) == 1 else None
            reflection_dir = trial_dir / "self-reflection-audit" if trial_dir else None
            feedback_path = reflection_dir / "self_reflection_feedback.json" if reflection_dir else None
            patch_path = reflection_dir / "self_reflection_patch.json" if reflection_dir else None
            learning_rows.append({
                **run_row,
                "task_id": task_id,
                "family_id": record.get("family_id") or spec.get("family_id"),
                "family_index": int(match.group(2)),
                "tier": int(match.group(3)),
                "task_slug": spec.get("task_slug"),
                "task_role": record.get("task_role") or spec.get("role"),
                "instruction": (record.get("retrieval") or {}).get("query_text"),
                "strict_pass": outcome.get("verifier_passed"),
                "reward": outcome.get("reward"),
                "normalized_score": outcome.get("normalized_score"),
                "outcome_pass": outcome.get("outcome_passed"),
                "process_pass": outcome.get("process_passed"),
                "classification": classify(outcome),
                "failed_tests": failed_tests,
                "reflection_status": reflection.get("status"),
                "reflection_mode": reflection.get("mode"),
                "learning_attempts": reflection.get("learning_attempts"),
                "repair_attempts": reflection.get("repair_attempts"),
                "initial_verifier_passed": reflection.get("initial_verifier_passed"),
                "terminal_verifier_passed": reflection.get("terminal_verifier_passed"),
                "repaired_to_pass": reflection.get("repaired_to_pass"),
                "same_session_verified": reflection.get("same_session_verified"),
                "all_attempts_same_session_verified": reflection.get("all_attempts_same_session_verified"),
                "reflection_feedback": (
                    load_optional_json(feedback_path)
                ),
                "reflection_patch": (
                    load_optional_json(patch_path)
                ),
                "local_trial_path": (
                    relative_or_absolute(trial_dir, raw_root) if trial_dir else None
                ),
                "local_reflection_path": (
                    relative_or_absolute(reflection_dir, raw_root)
                    if reflection_dir and reflection_dir.is_dir()
                    else None
                ),
                "record_path": relative_or_absolute(record_path, raw_root),
                "task_spec_path": spec.get("_path"),
            })

    # Repairs and reruns deliberately remain in the evidence file, but only one
    # run per model/condition/environment is used for aggregate conclusions.
    # Never blend tasks from different stateful episodes: prefer the run with
    # the most distinct T4-T6 records, then a platform-complete run, then the
    # newest AP timestamp.
    selected_keys = mark_selected_runs(runs, rows, skill_rows)
    for item in learning_rows:
        item["selected_run"] = (item["job_id"], item["run_id"]) in selected_keys

    selected_rows = [row for row in rows if row["selected_run"]]
    selected_learning_rows = [row for row in learning_rows if row["selected_run"]]
    summary_groups: dict[tuple[str, str, str, int], list[dict[str, Any]]] = defaultdict(list)
    for row in selected_rows:
        key = (row["model"], row["condition"], row["environment_id"], row["tier"])
        summary_groups[key].append(row)

    summaries: list[dict[str, Any]] = []
    for (model, condition, env, tier), group in sorted(summary_groups.items()):
        observed = len(group)
        classes = Counter(row["classification"] for row in group)
        summaries.append({
            "model": model,
            "condition": condition,
            "environment_id": env,
            "tier": tier,
            "observed_tasks": observed,
            "expected_tasks": 5,
            "coverage": observed / 5,
            "strict_passes": sum(row["strict_pass"] is True for row in group),
            "strict_pass_rate": sum(row["strict_pass"] is True for row in group) / observed,
            "outcome_passes": sum(row["outcome_pass"] is True for row in group),
            "outcome_pass_rate": sum(row["outcome_pass"] is True for row in group) / observed,
            "process_passes": sum(row["process_pass"] is True for row in group),
            "process_pass_rate": sum(row["process_pass"] is True for row in group) / observed,
            "classifications": dict(sorted(classes.items())),
        })

    return {
        "schema_version": "1.0",
        "generated_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "raw_root": str(raw_root.resolve()),
        "task_specs_root": str(tasks_root.resolve()),
        "curated_skills_root": str(skills_root.resolve()),
        "inventory_path": str(inventory_path.resolve()),
        "run_count": len(runs),
        "task_record_count": len(rows),
        "selected_run_count": len(selected_keys),
        "selected_task_record_count": len(selected_rows),
        "learning_record_count": len(learning_rows),
        "selected_learning_record_count": len(selected_learning_rows),
        "skill_pair_count": len(skill_rows),
        "runs": runs,
        "summaries": summaries,
        "tasks": rows,
        "learning_tasks": learning_rows,
        "skills": skill_rows,
    }


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    columns = [
        "model", "condition", "environment_id", "tier", "task_id",
        "task_slug", "classification", "strict_pass", "outcome_pass",
        "process_pass", "reward", "primary_skill", "required_skills",
        "retrieved_skill_ids", "skills_actually_used", "job_id", "ap_status",
        "selected_run", "oracle_injection_exact", "no_skill_empty",
        "curated_all_library_complete", "curated_all_visible_slugs",
        "curated_all_expected_slugs", "curated_all_library_errors",
        "record_path", "local_trial_path", "local_artifact_task_path",
        "local_trajectory_path",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=columns)
        writer.writeheader()
        for source in rows:
            row = {key: source.get(key) for key in columns}
            for key in (
                "required_skills",
                "retrieved_skill_ids",
                "skills_actually_used",
                "curated_all_visible_slugs",
                "curated_all_expected_slugs",
                "curated_all_library_errors",
            ):
                row[key] = json.dumps(row[key], ensure_ascii=False)
            writer.writerow(row)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-root", type=Path, required=True)
    parser.add_argument("--tasks-root", type=Path, default=Path("benchmark/tasks"))
    parser.add_argument("--skills-root", type=Path, default=Path("benchmark/skills"))
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    result = collect(args.raw_root, args.tasks_root, args.skills_root, args.inventory)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "t56_evidence.json"
    csv_path = args.output_dir / "t56_tasks.csv"
    json_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_csv(csv_path, result["tasks"])
    print(json.dumps({
        "json": str(json_path.resolve()),
        "csv": str(csv_path.resolve()),
        "run_count": result["run_count"],
        "task_record_count": result["task_record_count"],
        "selected_run_count": result["selected_run_count"],
        "selected_task_record_count": result["selected_task_record_count"],
        "learning_record_count": result["learning_record_count"],
        "selected_learning_record_count": result["selected_learning_record_count"],
        "skill_pair_count": result["skill_pair_count"],
        "summary_count": len(result["summaries"]),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
