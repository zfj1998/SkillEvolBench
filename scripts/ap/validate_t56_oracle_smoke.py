#!/usr/bin/env python3
"""Fail-closed validation for an exported exact-oracle T4-T6 AP job."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import yaml


def load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def tree_digest(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(
        (item for item in root.rglob("*") if item.is_file()),
        key=lambda item: item.relative_to(root).as_posix(),
    ):
        relative = path.relative_to(root).as_posix()
        digest.update(relative.encode("utf-8"))
        digest.update(b"\0")
        digest.update(path.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()


def projected_skill_digest(skill_md: bytes) -> str:
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
    """Accept post-run redaction only with a complete runtime hash chain."""
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

    try:
        manifest = load_json(output_root / "sanitization_manifest.json")
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


def require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def oracle_skill_use_audit(
    records: dict[str, dict[str, Any]],
    specs: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    rows: list[dict[str, Any]] = []
    for task_id in sorted(records):
        record = records[task_id]
        spec = specs[task_id]
        expected = (
            list(spec.get("required_skills") or [])
            if int(spec["task_index"]) == 6
            else [str(spec["primary_skill"])]
        )
        actual_value = record.get("skills_actually_used")
        require(
            isinstance(actual_value, list),
            f"skills_actually_used evidence is missing for {task_id}",
        )
        actual = sorted({str(item) for item in actual_value if item})
        missing = sorted(set(expected) - set(actual))
        unexpected = sorted(set(actual) - set(expected))
        require(
            not unexpected,
            f"oracle view leaked or misattributed skills for {task_id}: {unexpected}",
        )
        rows.append(
            {
                "task_id": task_id,
                "expected_skill_ids": expected,
                "skills_actually_used": actual,
                "missing_expected_skill_ids": missing,
                "full_use": not missing,
                "any_use": bool(actual),
            }
        )
    return {
        "task_count": len(rows),
        "full_use_count": sum(row["full_use"] for row in rows),
        "any_use_count": sum(row["any_use"] for row in rows),
        "no_use_count": sum(not row["any_use"] for row in rows),
        "rows": rows,
    }


def validate(export_root: Path, tasks_root: Path) -> dict[str, Any]:
    run_dirs = sorted(export_root.glob("artifacts/output/runs/*"))
    require(len(run_dirs) == 1, f"expected exactly one run directory, got {len(run_dirs)}")
    run_dir = run_dirs[0]
    config = load_json(run_dir / "config.json")
    manifest = load_json(export_root / "artifacts/output/ap_run_manifest.json")
    metrics = load_json(export_root / "artifacts/output/metrics.json")

    require(config.get("environment_id") == "E2", "smoke must target E2")
    require(config.get("evaluation_only_t4_t6") is True, "T4-T6 mode is not enabled")
    require(config.get("oracle_skill_view") is True, "exact oracle view is not enabled")
    require((config.get("baseline") or {}).get("name") == "curated_static", "baseline is not curated_static")
    require(manifest.get("canonical") is False, "diagnostic must be noncanonical")
    require(manifest.get("execution_scope") == "t4_t6_diagnostic", "wrong execution scope")
    require(manifest.get("benchmark_revision") == "d13fb39db6d5593d972fb70f07b56e7060438ee5", "unexpected benchmark revision")
    require(metrics.get("scoreable") is False, "diagnostic must be non-scoreable")
    require(metrics.get("task_score") == 0.0, "diagnostic task_score must be zero")
    require(metrics.get("expected_primary_trials") == 15, "expected_primary_trials must be 15")
    require(metrics.get("n_primary_trials") == 15, "n_primary_trials must be 15")

    specs: dict[str, dict[str, Any]] = {}
    skills_root = tasks_root.parent / "skills"
    for path in tasks_root.glob("*/task-spec.yaml"):
        spec = yaml.safe_load(path.read_text(encoding="utf-8"))
        if isinstance(spec, dict) and spec.get("environment_id") == "E2":
            specs[str(spec["task_id"])] = spec

    records_dir = run_dir / "stores/replay/records"
    record_paths = sorted(records_dir.glob("E2-LS*-T*.json"))
    task_ids = [path.stem for path in record_paths]
    expected = sorted(
        task_id
        for task_id, spec in specs.items()
        if int(spec.get("task_index", 0)) in {4, 5, 6}
    )
    require(task_ids == expected, "records are not exactly the 15 E2 T4-T6 tasks")
    require(not any("-T1" in task or "-T2" in task or "-T3" in task for task in task_ids), "learning task leaked into diagnostic")
    records = {path.stem: load_json(path) for path in record_paths}
    skill_use = oracle_skill_use_audit(records, specs)

    views_root = run_dir / "oracle-skill-views"
    audit_paths = sorted(views_root.glob("E2-LS*-T*.audit.json"))
    require(len(audit_paths) == 15, f"expected 15 oracle audits, got {len(audit_paths)}")
    verified_views: list[dict[str, Any]] = []
    for audit_path in audit_paths:
        audit = load_json(audit_path)
        task_id = str(audit.get("task_id"))
        require(task_id in expected, f"unexpected oracle audit task: {task_id}")
        spec = specs[task_id]
        expected_ids = (
            list(spec.get("required_skills") or [])
            if int(spec["task_index"]) == 6
            else [str(spec["primary_skill"])]
        )
        require(audit.get("oracle_skill_ids") == expected_ids, f"wrong oracle IDs for {task_id}")
        skills = audit.get("skills") or []
        require(len(skills) == len(expected_ids), f"wrong oracle skill count for {task_id}")
        view_dir = views_root / task_id
        require(view_dir.is_dir(), f"missing oracle view directory for {task_id}")
        visible_slugs = sorted(path.name for path in view_dir.iterdir() if path.is_dir())
        require(visible_slugs == sorted(skill.split(".", 1)[1] for skill in expected_ids), f"oracle view leaks or omits skills for {task_id}")
        for skill in skills:
            skill_dir = view_dir / str(skill["slug"])
            direct_match = tree_digest(skill_dir) == skill.get("sha256")
            sanitized_match = (
                not direct_match
                and sanitized_skill_matches_runtime_audit(
                    skill_dir=skill_dir,
                    audit_sha256=str(skill.get("sha256") or ""),
                    slug=str(skill.get("slug") or ""),
                    skills_root=skills_root,
                    output_root=export_root / "artifacts/output",
                )
            )
            require(
                direct_match or sanitized_match,
                f"oracle content hash mismatch for {task_id}/{skill.get('slug')}",
            )
            skill["content_verification"] = (
                "delivered_tree"
                if direct_match
                else "runtime_hash_via_sanitization_manifest"
            )
        verified_views.append({
            "task_id": task_id,
            "oracle_skill_ids": expected_ids,
            "content_verification": {
                str(skill["slug"]): skill["content_verification"]
                for skill in skills
            },
        })

    return {
        "valid": True,
        "run_id": config.get("run_id"),
        "environment_id": "E2",
        "benchmark_revision": manifest.get("benchmark_revision"),
        "record_count": len(record_paths),
        "oracle_audit_count": len(audit_paths),
        "scoreable": metrics.get("scoreable"),
        "task_score": metrics.get("task_score"),
        "verified_views": verified_views,
        "oracle_skill_use": skill_use,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("export_root", type=Path)
    parser.add_argument("--tasks-root", type=Path, default=Path("benchmark/tasks"))
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    try:
        result = validate(args.export_root, args.tasks_root)
    except (ValueError, OSError, json.JSONDecodeError, yaml.YAMLError) as exc:
        result = {"valid": False, "error": str(exc)}
        status = 1
    else:
        status = 0
    content = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(content, encoding="utf-8")
    print(content, end="")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
