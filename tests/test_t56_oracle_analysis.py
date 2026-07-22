from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).parents[1]


def load_script(name: str):
    path = ROOT / "scripts" / "ap" / name
    spec = importlib.util.spec_from_file_location(name.removesuffix(".py"), path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


COLLECTOR = load_script("build_t56_oracle_study.py")
AUDITOR = load_script("audit_t56_verifiers.py")
REPORT = load_script("build_t56_oracle_report.py")


def run(job: str, run_id: str, *, status: str, updated: str, env: str = "E1") -> dict:
    return {
        "job_id": job,
        "run_id": run_id,
        "model": "qwen3.7-max",
        "condition": "self_generated",
        "environment_id": env,
        "ap_status": status,
        "ap_updated_at": updated,
    }


def task(job: str, run_id: str, task_id: str) -> dict:
    return {"job_id": job, "run_id": run_id, "task_id": task_id}


def test_run_selection_never_blends_stateful_episodes() -> None:
    runs = [
        run("old", "r-old", status="Failed", updated="2026-01-01"),
        run("repair", "r-repair", status="Succeeded", updated="2026-01-02"),
        run("failed", "r-failed", status="Failed", updated="2026-01-03", env="E2"),
        run("success", "r-success", status="Succeeded", updated="2026-01-02", env="E2"),
    ]
    rows = [
        task("old", "r-old", "E1-LS1-T4"),
        task("old", "r-old", "E1-LS1-T5"),
        task("repair", "r-repair", "E1-LS1-T4"),
        task("failed", "r-failed", "E2-LS1-T4"),
        task("success", "r-success", "E2-LS1-T4"),
    ]

    selected = COLLECTOR.mark_selected_runs(runs, rows, [])

    assert selected == {("old", "r-old"), ("success", "r-success")}
    assert [row["task_id"] for row in rows if row["selected_run"]] == [
        "E1-LS1-T4",
        "E1-LS1-T5",
        "E2-LS1-T4",
    ]


def test_custom_score_weights_are_extracted_without_importing_task_code() -> None:
    path = ROOT / "benchmark/tasks/debug-ci-then-add-webhook/tests/score.py"
    dimensions = AUDITOR.score_dimensions(path)

    assert sum(item["weight"] for item in dimensions) == 100.0
    assert sum(item["weight"] for item in dimensions if item["kind"] == "process") == 45.0
    assert [item["name"] for item in dimensions if item["kind"] == "process"] == [
        "P1: all 3 bugs",
        "P2-P4: fix quality",
        "P5: HMAC",
    ]


def test_task_comparison_marks_oracle_outcome_rescue() -> None:
    common = {
        "model": "qwen3.7-max",
        "environment_id": "E2",
        "task_id": "E2-LS1-T5",
        "tier": 5,
        "task_slug": "sample",
        "primary_skill": "E2-LS1.example",
        "required_skills": [],
        "strict_pass": False,
        "process_pass": False,
        "normalized_score": 0.5,
        "classification": "outcome_and_process_failure",
        "failed_tests": [],
        "job_id": "job",
    }
    rows = [
        {**common, "condition": "self_generated", "outcome_pass": False},
        {
            **common,
            "condition": "exact_oracle",
            "strict_pass": True,
            "outcome_pass": True,
            "process_pass": True,
            "classification": "strict_pass",
        },
    ]

    comparison = next(
        item for item in REPORT.task_comparisons(rows)
        if item["model"] == "qwen3.7-max" and item["task_id"] == "E2-LS1-T5"
    )

    assert comparison["verdict"] == "oracle_rescues_outcome"
    assert comparison["conditions"]["no_skill"] is None


def test_coverage_is_fail_closed_for_missing_conditions() -> None:
    rows = [
        {
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "environment_id": "E1",
        }
        for _ in range(15)
    ]
    coverage = REPORT.condition_coverage(rows, [])

    assert len(coverage) == 36
    assert next(
        item for item in coverage
        if item["model"] == "qwen3.7-max"
        and item["condition"] == "self_generated"
        and item["environment_id"] == "E1"
    )["complete"] is True
    assert sum(item["complete"] for item in coverage) == 1


def test_oracle_injection_requires_exact_ids_dirs_and_hashes(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    view = run_dir / "oracle-skill-views/E2-LS1-T5/pre-call-parameter-validation"
    view.mkdir(parents=True)
    (view / "SKILL.md").write_text("oracle\n", encoding="utf-8")
    audit_path = run_dir / "oracle-skill-views/E2-LS1-T5.audit.json"
    audit_path.write_text(
        __import__("json").dumps({
            "oracle_skill_ids": ["E2-LS1.pre-call-parameter-validation"],
            "skills": [{
                "slug": "pre-call-parameter-validation",
                "sha256": COLLECTOR.tree_digest(view),
            }],
        }),
        encoding="utf-8",
    )
    spec = {
        "task_index": 5,
        "primary_skill": "E2-LS1.pre-call-parameter-validation",
    }

    evidence = COLLECTOR.oracle_evidence(
        run_dir, "E2-LS1-T5", spec, True, tmp_path
    )
    assert evidence["oracle_injection_exact"] is True

    (view / "extra.txt").write_text("tamper\n", encoding="utf-8")
    evidence = COLLECTOR.oracle_evidence(
        run_dir, "E2-LS1-T5", spec, True, tmp_path
    )
    assert evidence["oracle_injection_exact"] is False
    assert evidence["oracle_injection_errors"] == [
        "oracle content hash mismatch: pre-call-parameter-validation"
    ]


def test_learning_analysis_tracks_repair_and_verifier_overfit_markers() -> None:
    evidence = {
        "learning_tasks": [{
            "selected_run": True,
            "model": "qwen3.7-max",
            "family_id": "E2-LS1",
            "instruction": "validate a request before sending it",
            "failed_tests": [{"name": "validation_before_fetch"}],
            "reflection_feedback": {"message": "process test failed"},
            "learning_attempts": 3,
            "terminal_verifier_passed": True,
            "repaired_to_pass": True,
            "all_attempts_same_session_verified": True,
        }],
        "skills": [{
            "selected_run": True,
            "condition": "self_generated",
            "model": "qwen3.7-max",
            "environment_id": "E2",
            "family_id": "E2-LS1",
            "skill_slug": "validate-request",
            "current_version": 1,
            "expected_oracle_skill_slug": "pre-call-parameter-validation",
            "word_jaccard": 0.25,
            "generated_text": "Use validation. The process test scans source-visible literals.",
            "curated_text": "Validate request parameters before sending.",
        }],
    }

    result = REPORT.learning_analysis(evidence)

    assert result["by_model"]["qwen3.7-max"]["learning_attempts"] == 3
    assert result["by_model"]["qwen3.7-max"]["repaired_to_pass"] == 1
    assert result["by_model"]["qwen3.7-max"]["skills_with_verifier_markers"] == 1
    family = result["families"][0]
    assert family["generated_verifier_marker_hits"] == 2
    assert family["oracle_token_recall_from_learning_evidence"] is not None


def test_model_comparison_uses_only_same_task_pairs() -> None:
    rows = [
        {"model": "qwen3.7-max", "condition": "self_generated", "task_id": "a", "tier": 5, "strict_pass": True, "outcome_pass": True, "process_pass": True},
        {"model": "sig-fable", "condition": "self_generated", "task_id": "a", "tier": 5, "strict_pass": False, "outcome_pass": True, "process_pass": False},
        {"model": "qwen3.7-max", "condition": "self_generated", "task_id": "qwen-only", "tier": 5, "strict_pass": True, "outcome_pass": True, "process_pass": True},
    ]

    strict = next(
        item for item in REPORT.model_comparisons(rows)
        if item["condition"] == "self_generated"
        and item["tier"] == 5
        and item["metric"] == "strict"
    )

    assert strict["n"] == 1
    assert strict["qwen_pass"] == 1
    assert strict["fable_pass"] == 0
    assert strict["qwen_only"] == 1
    assert strict["sign_test_p"] == 1.0


def test_reference_integrity_requires_exact_90_task_grid() -> None:
    rows = [
        {
            "task_id": f"E{environment}-LS{family}-T{tier}",
            "environment_id": f"E{environment}",
            "tier": tier,
            "strict_pass": True,
        }
        for environment in range(1, 7)
        for family in range(1, 6)
        for tier in (4, 5, 6)
    ]
    result = REPORT.reference_integrity_analysis({"tasks": rows})
    assert result["complete"] is True
    assert result["all_reference_solutions_pass"] is True
    assert result["passed"] == result["total"] == 90

    rows[-1]["strict_pass"] = False
    result = REPORT.reference_integrity_analysis({"tasks": rows})
    assert result["complete"] is True
    assert result["all_reference_solutions_pass"] is False
    assert result["passed"] == 89
    assert [row["task_id"] for row in result["failures"]] == ["E6-LS5-T6"]

    result = REPORT.reference_integrity_analysis({"tasks": rows[:-1]})
    assert result["complete"] is False
    assert result["total"] == 89


def test_failure_attribution_separates_functional_and_verified_false_negative() -> None:
    common = {
        "selected_run": True,
        "condition": "self_generated",
        "model": "qwen3.7-max",
        "environment_id": "E2",
        "tier": 5,
        "strict_pass": False,
        "failed_tests": [],
    }
    rows = [
        {
            **common,
            "task_id": "E2-LS1-T5",
            "task_slug": "known-shape-case",
            "outcome_pass": True,
            "process_pass": False,
            "classification": "process_only_failure",
        },
        {
            **common,
            "task_id": "E2-LS3-T5",
            "task_slug": "functional-case",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
    ]
    audit = {
        "tasks": [
            {"task_id": "E2-LS1-T5", "process_shape_sensitivity": "high"},
            {"task_id": "E2-LS3-T5", "process_shape_sensitivity": "low"},
        ]
    }
    result = REPORT.failure_attribution(
        rows,
        audit,
        {"complete": False, "failures": []},
    )
    causes = {row["task_id"]: row["cause"] for row in result["failures"]}
    assert causes == {
        "E2-LS1-T5": "verified_verifier_false_negative",
        "E2-LS3-T5": "functional_gap",
    }


def test_oracle_scope_audit_flags_explicit_basic_vs_advanced_gap(tmp_path: Path) -> None:
    tasks_root = tmp_path / "benchmark/tasks"
    skill_root = tmp_path / "benchmark/skills/retry"
    tasks_root.mkdir(parents=True)
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "# Retry\n\nScope: simple fixed-delay retry for synchronous HTTP calls.\n",
        encoding="utf-8",
    )
    audit = {
        "tasks_root": str(tasks_root),
        "tasks": [{
            "task_id": "E2-LS2-T5",
            "environment_id": "E2",
            "tier": 5,
            "task_slug": "advanced-retry",
            "primary_skill": "E2-LS2.retry",
            "required_skills": [],
            "instruction": "Implement exponential backoff with jitter.",
            "process": {"check_names": ["uses_exponential_backoff", "adds_jitter"]},
            "outcome": {"check_names": []},
        }],
    }

    result = REPORT.oracle_scope_analysis(audit)

    assert result["counts"] == {"high": 1}
    assert result["rows"][0]["missing_concepts"] == [
        "exponential backoff",
        "jitter",
    ]
