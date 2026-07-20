from __future__ import annotations

import json
import subprocess
from pathlib import Path

import yaml

from scripts.audit_skill_utility import (
    audit_run,
    build_report,
    discover_run_dirs,
    render_markdown,
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _write_jsonl(path: Path, values: list[dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(value) + "\n" for value in values),
        encoding="utf-8",
    )


def _git(library: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", str(library), *args],
        check=True,
        stdout=subprocess.PIPE,
        text=True,
    )
    return completed.stdout.strip()


def _make_run(tmp_path: Path) -> Path:
    run = (
        tmp_path
        / "jobs"
        / "ap-skillevolbench-example-o4"
        / "artifacts"
        / "output"
        / "runs"
        / "run-1"
    )
    records = run / "stores" / "replay" / "records"
    skill_id = "E1-LS1.debug-pattern"
    common = {"env_id": "E1", "family_id": "E1-LS1", "replay_mode": "primary"}
    _write_json(
        records / "E1-LS1-T1.json",
        {
            **common,
            "task_id": "E1-LS1-T1",
            "task_role": "canonical",
            "timestamp": "2026-01-01T00:00:01Z",
            "library_hash_pre": "before",
            "outcome": {"verifier_passed": False, "reward": 0.0},
            "retrieval": {"query_text": "input one", "skills": []},
            "skills_actually_used": [],
            "reflection": {
                "status": "completed",
                "patch_id": "patch-1",
                "same_session_verified": True,
            },
        },
    )
    _write_json(
        records / "E1-LS1-T2.json",
        {
            **common,
            "task_id": "E1-LS1-T2",
            "task_role": "enriched",
            "timestamp": "2026-01-01T00:00:02Z",
            "library_hash_pre": "after-patch-1",
            "outcome": {"verifier_passed": True, "reward": 1.0},
            "retrieval": {
                "query_text": "input two",
                "skills": [{"skill_id": skill_id}],
            },
            "skills_actually_used": [skill_id],
            "reflection": {
                "status": "rejected",
                "reason": "skill_frontmatter_invalid:debug-pattern",
                "same_session_verified": True,
            },
        },
    )
    _write_json(
        records / "E1-LS1-T3.json",
        {
            **common,
            "task_id": "E1-LS1-T3",
            "task_role": "variant",
            "timestamp": "2026-01-01T00:00:03Z",
            "library_hash_pre": "after-patch-1",
            "outcome": {"verifier_passed": False, "reward": 0.25},
            "retrieval": {
                "query_text": "input three",
                "skills": [{"skill_id": skill_id}],
            },
            "skills_actually_used": [skill_id],
            "reflection": {},
        },
    )

    _write_jsonl(
        run / "stores" / "events" / "patches.jsonl",
        [
            {
                "event_type": "patch_proposed",
                "patch_id": "patch-1",
                "target_skill_ids": [skill_id],
                "operation_type": "create",
                "summary": "general debug workflow",
            },
            {
                "event_type": "patch_applied",
                "patch_id": "patch-1",
                "apply_result": {
                    "affected_skill_ids": [skill_id],
                    "commit_hash": "COMMIT_PLACEHOLDER",
                },
            },
        ],
    )
    _write_jsonl(
        run / "stores" / "events" / "lifecycle.jsonl",
        [
            {
                "event_type": "trial_ended_learning",
                "task_id": "E1-LS1-T1",
                "library_hash_after": "after-patch-1",
            },
            {
                "event_type": "trial_ended_learning",
                "task_id": "E1-LS1-T2",
                "library_hash_after": "after-patch-1",
            },
        ],
    )

    audit_root = run / "harbor-job" / "run-1"
    audit_t1 = audit_root / "E1-LS1-T1__abc" / "self-reflection-audit"
    _write_json(
        audit_t1 / "self_reflection_result.json",
        {
            "task_id": "E1-LS1-T1",
            "status": "completed",
            "patch_id": "patch-1",
            "same_session_verified": True,
        },
    )
    _write_json(
        audit_t1 / "self_reflection_patch.json",
        {
            "summary": "general debug workflow",
            "operation_type": "create",
            "upsert_files": {
                "debug-pattern/SKILL.md": (
                    "---\nname: debug-pattern\ndescription: Reusable debugging steps.\n---\n"
                    "\n# Debug pattern\n"
                )
            },
            "delete_paths": [],
        },
    )
    audit_t2 = audit_root / "E1-LS1-T2__def" / "self-reflection-audit"
    _write_json(
        audit_t2 / "self_reflection_result.json",
        {
            "task_id": "E1-LS1-T2",
            "status": "rejected",
            "reason": "skill_frontmatter_invalid:debug-pattern",
            "same_session_verified": True,
        },
    )
    _write_jsonl(
        audit_t2 / "opencode.reflection.jsonl",
        [{"type": "text", "text": "wrote self_reflection_patch.json"}],
    )

    library = run / "library" / "E1"
    (library / "active" / "debug-pattern").mkdir(parents=True)
    (library / "active" / "debug-pattern" / "SKILL.md").write_text(
        "---\nname: debug-pattern\ndescription: Reusable debugging steps.\n---\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q", "-b", "main", str(library)], check=True)
    _git(library, "config", "user.email", "audit@example.invalid")
    _git(library, "config", "user.name", "Audit Test")
    _git(library, "add", ".")
    _git(library, "commit", "-q", "-m", "add reflected skill")
    commit = _git(library, "rev-parse", "HEAD")
    manifest = {
        "schema_version": 1,
        "skills": {
            skill_id: {
                "name": "debug-pattern",
                "status": "active",
                "current_version": 1,
                "versions": [
                    {
                        "version": 1,
                        "parent_version": None,
                        "patch_id": "patch-1",
                        "created_at_task": "E1-LS1-T1",
                        "git_commit": commit,
                    }
                ],
            }
        },
    }
    (library / "manifest.yaml").write_text(yaml.safe_dump(manifest), encoding="utf-8")

    patch_path = run / "stores" / "events" / "patches.jsonl"
    patch_path.write_text(
        patch_path.read_text(encoding="utf-8").replace("COMMIT_PLACEHOLDER", commit),
        encoding="utf-8",
    )
    return run


def test_audit_links_patch_version_retrieval_and_next_outcome(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    audited = audit_run(run)

    assert audited["n_primary_records"] == 3
    assert len(audited["chains"]) == 2
    applied, rejected = audited["chains"]
    assert applied["transition"] == "fail_to_success"
    assert applied["different_input_proven"] is True
    assert applied["patch_applied"] is True
    assert applied["skill_version_recorded"] is True
    assert applied["patch_apply_commit_exists"] is True
    assert applied["patch_state_visible_to_next_task"] is True
    assert applied["patch_skill_retrieved_next"] is True
    assert applied["patch_skill_used_next"] is True
    assert applied["candidate"]["basic_skill_syntax_valid"] is True

    assert rejected["transition"] == "success_to_fail"
    assert rejected["candidate"]["present"] is False
    assert rejected["candidate"]["basic_skill_syntax_valid"] is False
    assert rejected["candidate_stream_mentions_patch_file"] is True
    assert audited["warnings"]


def test_group_discovery_and_aggregate_are_read_only(tmp_path: Path) -> None:
    run = _make_run(tmp_path)
    group_root = tmp_path
    assert discover_run_dirs([group_root]) == [run.resolve()]

    report = build_report([run])
    aggregate = report["aggregate"]
    assert aggregate["transition_counts"]["fail_to_success"] == 1
    assert aggregate["transition_counts"]["success_to_fail"] == 1
    assert aggregate["n_applied_patches_retrieved_on_next_input"] == 1
    assert "observational, not causal" in report["claim_boundary"]
    markdown = render_markdown(report)
    assert "Manual content-quality rubric" in markdown
    assert "E1-LS1-T1" in markdown
