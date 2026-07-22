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

    assert len(coverage) == 48
    assert next(
        item for item in coverage
        if item["model"] == "qwen3.7-max"
        and item["condition"] == "self_generated"
        and item["environment_id"] == "E1"
    )["complete"] is True
    assert sum(item["complete"] for item in coverage) == 1


def test_curated_all_condition_requires_five_exact_frozen_skills(
    tmp_path: Path,
) -> None:
    skills_root = tmp_path / "benchmark/skills"
    run_dir = tmp_path / "run"
    active = run_dir / "library/E1/active"
    specs = {}
    for family in range(1, 6):
        slug = f"skill-{family}"
        source = skills_root / slug
        visible = active / slug
        source.mkdir(parents=True)
        visible.mkdir(parents=True)
        content = f"# Skill {family}\n"
        (source / "SKILL.md").write_text(content, encoding="utf-8")
        (visible / "SKILL.md").write_text(content, encoding="utf-8")
        specs[f"E1-LS{family}-T4"] = {
            "environment_id": "E1",
            "family_id": f"E1-LS{family}",
            "latent_skill_id": f"E1-LS{family}.{slug}",
        }
    (active.parent / ".frozen").write_text("frozen\n", encoding="utf-8")

    valid = COLLECTOR.curated_all_evidence(run_dir, "E1", specs, skills_root)

    assert valid["curated_all_library_complete"] is True
    assert valid["curated_all_library_errors"] == []
    assert COLLECTOR.condition_name(
        {"baseline": {"name": "curated_static"}, "oracle_skill_view": False}
    ) == "curated_all"

    (active / "skill-3/SKILL.md").write_text("tampered\n", encoding="utf-8")
    invalid = COLLECTOR.curated_all_evidence(run_dir, "E1", specs, skills_root)
    assert invalid["curated_all_library_complete"] is False
    assert invalid["curated_all_library_errors"] == [
        "curated content mismatch: skill-3"
    ]


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


def test_environment_diagnostics_keeps_reference_and_model_controls_distinct() -> None:
    rows = [
        {
            "model": model,
            "condition": "self_generated",
            "environment_id": "E2",
            "task_id": "E2-LS1-T5",
            "tier": 5,
            "strict_pass": False,
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        }
        for model in REPORT.MODELS
    ] + [
        {
            "model": model,
            "condition": "exact_oracle",
            "environment_id": "E2",
            "task_id": "E2-LS1-T5",
            "tier": 5,
            "strict_pass": True,
            "outcome_pass": True,
            "process_pass": True,
            "classification": "strict_pass",
        }
        for model in REPORT.MODELS
    ]
    comparisons = [{
        "environment_id": "E2",
        "tier": 5,
        "verdict": "oracle_rescues_outcome",
        "conditions": {"exact_oracle": {"outcome": True}},
    }]
    oracle_scope = {"rows": [{
        "environment_id": "E2",
        "scope_risk": "high",
        "instruction_concepts": ["jitter"],
        "verifier_only_concepts": [],
    }]}
    attribution = {"failures": [{
        "environment_id": "E2",
        "cause": "functional_gap",
    }]}
    reference = {"rows": [
        {"environment_id": "E2", "tier": 5, "passed": 5, "total": 5},
        {"environment_id": "E2", "tier": 6, "passed": 5, "total": 5},
    ]}

    result = REPORT.environment_diagnostics(
        rows, comparisons, oracle_scope, attribution, reference
    )
    e2 = next(row for row in result if row["environment_id"] == "E2")

    assert e2["both_models_outcome_fail"] == 1
    assert e2["reference_strict_passed"] == 10
    assert e2["reference_total"] == 10
    assert e2["controls"]["exact_oracle"] == {
        "observed": 2,
        "strict_passed": 2,
        "outcome_passed": 2,
        "process_passed": 2,
    }
    assert e2["status"] == "provisional"
    assert e2["oracle_outcome_rescues"] == 1
    assert REPORT.compact_message("a\n  b", limit=10) == "a b"

    complete_rows = [
        {
            "model": model,
            "condition": condition,
            "environment_id": "E2",
            "task_id": f"E2-LS{index % 5 + 1}-T{5 + index // 5}",
            "tier": 5 + index // 5,
            "strict_pass": condition == "exact_oracle",
            "outcome_pass": condition in {"self_generated", "exact_oracle"},
            "process_pass": condition == "exact_oracle",
            "classification": (
                "strict_pass" if condition == "exact_oracle"
                else "process_only_failure" if condition == "self_generated"
                else "outcome_and_process_failure"
            ),
        }
        for condition in ("self_generated", "exact_oracle", "curated_all", "no_skill")
        for model in REPORT.MODELS
        for index in range(10)
    ]
    complete = REPORT.environment_diagnostics(
        complete_rows, [], oracle_scope, attribution, reference
    )
    e2_complete = next(row for row in complete if row["environment_id"] == "E2")
    assert e2_complete["status"] == "matched_controls_complete"
    assert "self-generated 20/20" in e2_complete["current_read"]
    assert "exact-oracle 20/20" in e2_complete["current_read"]
    assert "选择先验效应 +20 题" in e2_complete["current_read"]


def test_oracle_case_studies_use_only_the_declared_condition(tmp_path: Path) -> None:
    common = {
        "task_id": "E2-LS1-T6",
        "model": "sig-fable",
        "strict_pass": False,
        "outcome_pass": False,
        "process_pass": False,
        "normalized_score": 0.5,
        "failed_process_tests": [],
    }
    cases = REPORT.build_cases(
        [
            {**common, "condition": "self_generated"},
            {**common, "condition": "exact_oracle"},
        ],
        {"tasks": [{"task_id": "E2-LS1-T6", "process": {}}]},
        tmp_path,
    )

    case = next(item for item in cases if item["task_id"] == "E2-LS1-T6")
    assert [row["condition"] for row in case["observations"]] == ["exact_oracle"]


def test_oracle_scope_audit_flags_explicit_basic_vs_advanced_gap(tmp_path: Path) -> None:
    tasks_root = tmp_path / "benchmark/tasks"
    skill_root = tmp_path / "benchmark/skills/retry"
    tasks_root.mkdir(parents=True)
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text(
        "# Retry\n\nScope: simple fixed-delay retry for synchronous HTTP calls.\n",
        encoding="utf-8",
    )
    (skill_root / "meta.yaml").write_text(
        "gap_1_summary: Add exponential backoff with jitter.\n",
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
    assert result["rows"][0]["task_concepts_in_author_gaps"] == [
        "exponential backoff",
        "jitter",
    ]
    assert result["concept_visibility"] == {
        "task_count": 1,
        "tasks_with_controlled_concepts": 1,
        "concept_instances": 2,
        "instruction_explicit_instances": 2,
        "verifier_only_instances": 0,
        "tasks_with_verifier_only_concepts": 0,
        "author_gap_metadata_instances": 2,
        "tasks_with_author_gap_metadata_hits": 1,
    }


def test_oracle_scope_separates_instruction_from_verifier_only_concepts(
    tmp_path: Path,
) -> None:
    tasks_root = tmp_path / "benchmark/tasks"
    skill_root = tmp_path / "benchmark/skills/retry"
    tasks_root.mkdir(parents=True)
    skill_root.mkdir(parents=True)
    (skill_root / "SKILL.md").write_text("# Retry\n", encoding="utf-8")
    audit = {
        "tasks_root": str(tasks_root),
        "tasks": [{
            "task_id": "E2-LS2-T5",
            "environment_id": "E2",
            "tier": 5,
            "task_slug": "hidden-token-refresh",
            "primary_skill": "E2-LS2.retry",
            "required_skills": [],
            "instruction": "Handle an expired authentication response.",
            "process": {"check_names": ["checks_token_expired_reason"]},
            "outcome": {"check_names": []},
        }],
    }

    result = REPORT.oracle_scope_analysis(audit)

    row = result["rows"][0]
    assert row["instruction_concepts"] == []
    assert row["verifier_only_concepts"] == ["token refresh"]
    assert result["concept_visibility"]["verifier_only_instances"] == 1


def test_derivability_analysis_keeps_all_three_sources_distinct() -> None:
    concepts = [
        "visible-captured",
        "visible-oracle-only",
        "visible-missing-both",
        "unseen-both-skills",
        "unseen-oracle-only",
        "unseen-generated-only",
        "missing-everywhere",
    ]
    learning = {
        "families": [{
            "model": "qwen3.7-max",
            "family_id": "E1-LS1",
            "learning_concepts": concepts[:3],
            "generated_concepts": [
                "visible-captured",
                "unseen-both-skills",
                "unseen-generated-only",
            ],
            "curated_concepts": [
                "visible-oracle-only",
                "unseen-both-skills",
                "unseen-oracle-only",
            ],
        }],
    }
    oracle_scope = {
        "rows": [{
            "task_id": "E1-LS1-T5",
            "environment_id": "E1",
            "tier": 5,
            "task_concepts": concepts,
            "oracle_concepts": [
                "visible-oracle-only",
                "unseen-both-skills",
                "unseen-oracle-only",
            ],
            "author_gap_concepts": ["unseen-oracle-only", "missing-everywhere"],
        }],
    }

    result = REPORT.derivability_analysis(learning, oracle_scope)

    assert {
        row["concept"]: row["category"] for row in result["records"]
    } == {
        "visible-captured": "captured_from_visible_evidence",
        "visible-oracle-only": "oracle_captures_visible_generated_misses",
        "visible-missing-both": "visible_missing_from_both_skills",
        "unseen-both-skills": "both_skills_add_unseen_concept",
        "unseen-oracle-only": "oracle_adds_unseen_concept",
        "unseen-generated-only": "model_adds_beyond_visible_evidence",
        "missing-everywhere": "missing_from_both_learning_and_oracle",
    }
    qwen = next(
        row for row in result["summaries"] if row["model"] == "qwen3.7-max"
    )
    assert qwen["concept_instances"] == 7
    assert set(qwen["category_counts"].values()) == {1}
    assert qwen["author_gap_metadata_hits"] == 2
    assert qwen["author_gap_unseen_in_t1_t3"] == 2
    assert qwen["author_gap_missing_from_all_model_visible_sources"] == 1


def test_t6_derivability_unions_all_required_skill_families() -> None:
    learning = {
        "families": [
            {
                "model": "qwen3.7-max",
                "family_id": "E3-LS2",
                "learning_concepts": [],
                "generated_concepts": [],
            },
            {
                "model": "qwen3.7-max",
                "family_id": "E3-LS3",
                "learning_concepts": ["deduplication"],
                "generated_concepts": ["deduplication"],
            },
        ]
    }
    oracle_scope = {
        "rows": [{
            "task_id": "E3-LS2-T6",
            "environment_id": "E3",
            "tier": 6,
            "oracle_skill_ids": [
                "E3-LS2.type-normalization-before-sort",
                "E3-LS3.key-alignment-before-merge",
            ],
            "task_concepts": ["deduplication"],
            "oracle_concepts": [],
            "author_gap_concepts": ["deduplication"],
        }]
    }

    result = REPORT.derivability_analysis(learning, oracle_scope)

    assert len(result["records"]) == 1
    row = result["records"][0]
    assert row["category"] == "captured_from_visible_evidence"
    assert row["source_family_ids"] == ["E3-LS2", "E3-LS3"]
    assert row["in_t1_t3_evidence"] is True
    assert row["in_generated_skill"] is True
