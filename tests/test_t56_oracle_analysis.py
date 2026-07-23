from __future__ import annotations

import importlib.util
import json
import zipfile
from pathlib import Path
from types import SimpleNamespace


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
MATRIX = load_script("watch_t56_oracle_matrix.py")
QWEN_REPAIR = load_script("watch_qwen_e6_then_e1.py")
ORACLE_VALIDATOR = load_script("validate_t56_oracle_smoke.py")


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


def test_matrix_watcher_fable_gate_does_not_block_qwen_lane() -> None:
    watcher = object.__new__(MATRIX.MatrixWatcher)
    watcher.state = {
        "stages": {
            name: {"status": "pending", "group_id": None}
            for name in MATRIX.STAGE_NAMES
        },
        "fable_e4_repair": {"status": "pending", "job_id": None},
    }
    submitted: list[str] = []
    heartbeats: list[tuple[str, dict]] = []
    watcher.update_submitted_stages = lambda: None
    watcher.qwen_ready = lambda: (True, "Qwen repairs terminal")
    watcher.advance_e4_repair = lambda: (
        False,
        "Fable exact-oracle smoke still running",
    )
    watcher.prerequisites = lambda: (False, "Fable prerequisites still running")
    watcher.submit = submitted.append
    watcher.save = lambda: None
    watcher.heartbeat = lambda phase, **fields: heartbeats.append((phase, fields))

    watcher.step()

    assert submitted == ["qwen_exact_oracle"]
    assert heartbeats == [
        (
            "monitoring_matrix",
            {
                "qwen_gate": "Qwen repairs terminal",
                "fable_gate": "Fable prerequisites still running",
                "fable_e4_repair_reason": (
                    "Fable exact-oracle smoke still running"
                ),
            },
        )
    ]


def qwen_repair_watcher(tmp_path: Path):
    watcher = object.__new__(QWEN_REPAIR.Watcher)
    watcher.args = SimpleNamespace(cluster="hk-benchmark-dev", poll_sec=45)
    watcher.state_dir = tmp_path
    watcher.control_path = tmp_path / "control.json"
    watcher.control = {}
    watcher.secrets = []
    return watcher


def test_qwen_repair_watcher_retries_failed_ap_job(tmp_path: Path) -> None:
    watcher = qwen_repair_watcher(tmp_path)
    old_key = "00000000-0000-4000-8000-000000000001"
    (tmp_path / "idempotency_key.txt").write_text(old_key + "\n", encoding="utf-8")
    QWEN_REPAIR.write_json(
        tmp_path / "submission.json",
        {"job_id": "failed-e1", "status": "Running"},
    )
    watcher.get_job = lambda job_id: {"job_id": job_id, "status": "Failed"}

    completed = watcher.monitor_e1("failed-e1")

    assert completed is False
    assert not (tmp_path / "submission.json").exists()
    assert not (tmp_path / "idempotency_key.txt").exists()
    assert watcher.control["failed_e1_jobs"][0]["job_id"] == "failed-e1"
    assert "repair_exhausted" not in watcher.control
    heartbeat = QWEN_REPAIR.read_json(tmp_path / "heartbeat.json", {})
    assert heartbeat["watcher_phase"] == "e1_repair_backoff"


def test_qwen_repair_watcher_stays_alive_after_retry_budget(tmp_path: Path) -> None:
    watcher = qwen_repair_watcher(tmp_path)
    watcher.control["failed_e1_jobs"] = [
        {"job_id": "failed-1", "status": "Failed"},
        {"job_id": "failed-2", "status": "Failed"},
    ]
    QWEN_REPAIR.write_json(
        tmp_path / "submission.json",
        {"job_id": "failed-3", "status": "Running"},
    )
    watcher.get_job = lambda job_id: {"job_id": job_id, "status": "Failed"}

    completed = watcher.monitor_e1("failed-3")

    assert completed is False
    assert watcher.control["repair_exhausted"] is True
    assert (tmp_path / "submission.json").exists()
    heartbeat = QWEN_REPAIR.read_json(tmp_path / "heartbeat.json", {})
    assert heartbeat["watcher_phase"] == "repair_exhausted"


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
    assert comparison["causal"]["category"] == "awaiting_four_conditions"


def causal_conditions(self_pass: bool, exact: bool, all_skills: bool, none: bool):
    return {
        "self_generated": {"outcome": self_pass},
        "exact_oracle": {"outcome": exact},
        "curated_all": {"outcome": all_skills},
        "no_skill": {"outcome": none},
    }


def test_four_condition_causal_diagnosis_distinguishes_skill_effects() -> None:
    cases = {
        (True, True, True, True): "low_skill_demand",
        (True, False, False, False): "self_evolution_benefit",
        (False, True, True, False): "curated_content_benefit_generated_gap",
        (False, True, False, False): "annotation_selection_prior",
        (False, False, True, False): "all_library_helps_gold_subset_insufficient",
        (False, False, False, True): "self_generated_harm",
        (False, False, False, False): "all_model_conditions_fail",
    }
    for outcomes, expected in cases.items():
        diagnosis = REPORT.causal_diagnosis(causal_conditions(*outcomes))
        assert diagnosis["complete"] is True
        assert diagnosis["category"] == expected
        assert diagnosis["pattern"].startswith("S=")


def test_causal_measurement_gate_excludes_known_benchmark_defects() -> None:
    contaminated = REPORT.causal_measurement_annotation(
        "qwen3.7-max", "E4-LS2-T6"
    )
    clean = REPORT.causal_measurement_annotation(
        "qwen3.7-max", "E1-LS1-T5"
    )

    assert contaminated["measurement_status"] == "known_contamination"
    assert contaminated["causal_interpretable"] is False
    assert "benchmark/verifier" in contaminated["measurement_warning"]
    assert clean["measurement_status"] == "no_known_outcome_defect"
    assert clean["causal_interpretable"] is True


def test_causal_summary_separates_raw_and_interpretable_counts() -> None:
    comparisons = [
        {
            "tier": 5,
            "causal": {
                "complete": True,
                "category": "self_evolution_benefit",
                "causal_interpretable": True,
            },
        },
        {
            "tier": 6,
            "causal": {
                "complete": True,
                "category": "self_evolution_benefit",
                "causal_interpretable": False,
            },
        },
        {
            "tier": 4,
            "causal": {
                "complete": True,
                "category": "low_skill_demand",
                "causal_interpretable": True,
            },
        },
    ]

    result = REPORT.causal_diagnosis_summary(comparisons)

    assert result["complete"] == 2
    assert result["interpretable_complete"] == 1
    assert result["measurement_contaminated_complete"] == 1
    assert result["category_counts"] == {"self_evolution_benefit": 2}
    assert result["interpretable_category_counts"] == {
        "self_evolution_benefit": 1
    }


def test_skill_use_adherence_tracks_exact_oracle_compliance() -> None:
    rows = [
        {
            "model": "qwen3.7-max",
            "condition": "exact_oracle",
            "tier": 6,
            "oracle_skill_ids": ["a", "b"],
            "skills_actually_used": ["a", "b"],
            "outcome_pass": True,
        },
        {
            "model": "qwen3.7-max",
            "condition": "exact_oracle",
            "tier": 6,
            "oracle_skill_ids": ["a", "b"],
            "skills_actually_used": ["a"],
            "outcome_pass": False,
        },
    ]

    result = next(
        row
        for row in REPORT.skill_use_adherence(rows)
        if row["model"] == "qwen3.7-max"
        and row["condition"] == "exact_oracle"
        and row["tier"] == 6
    )

    assert result["n"] == 2
    assert result["any_skill_used"] == 2
    assert result["exact_expected_skills_fully_used"] == 1
    assert result["used_outcome_passed"] == 1
    assert result["unused_n"] == 0


def test_coverage_is_fail_closed_for_missing_conditions() -> None:
    rows = [
        {
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "environment_id": "E1",
            "task_id": f"E1-LS{family}-T{tier}",
        }
        for family in range(1, 6)
        for tier in range(4, 7)
    ]
    expected_ids = [row["task_id"] for row in rows]
    runs = [
        {
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "environment_id": "E1",
            "job_id": "job-e1",
            "run_id": "run-e1",
            "ap_status": "Succeeded",
            "order_seed": "A",
            "within_env_replay": False,
            "replay_eval": False,
            "library_scope": "environment",
            "lifecycle_parse_errors": [],
            "evaluation_task_start_count": 15,
            "evaluation_task_end_count": 15,
            "evaluation_task_ids": expected_ids,
            "library_frozen_before_evaluation": True,
            "evaluation_library_hash_stable": True,
            "evaluation_library_hashes": ["stable"],
            "baseline": "selfgen_in_session_always",
            "evaluation_only_t4_t6": False,
            "oracle_skill_view": False,
            "use_skill_library": True,
            "skill_init": "empty",
            "allow_curated_inject": False,
            "learning_max_attempts": 3,
            "learning_record_count": 15,
        }
    ]
    coverage = REPORT.condition_coverage(rows, runs)

    assert len(coverage) == 48
    assert next(
        item for item in coverage
        if item["model"] == "qwen3.7-max"
        and item["condition"] == "self_generated"
        and item["environment_id"] == "E1"
    )["complete"] is True
    assert sum(item["complete"] for item in coverage) == 1

    runs[0]["evaluation_library_hash_stable"] = False
    invalid = REPORT.condition_coverage(rows, runs)
    invalid_cell = next(
        item
        for item in invalid
        if item["model"] == "qwen3.7-max"
        and item["condition"] == "self_generated"
        and item["environment_id"] == "E1"
    )
    assert invalid_cell["complete"] is False
    assert invalid_cell["protocol_errors"] == [
        "evaluation library hash was not stable"
    ]


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
    events = run_dir / "stores/events/lifecycle.jsonl"
    events.parent.mkdir(parents=True)
    events.write_text(
        "\n".join(
            [
                json.dumps(
                    {
                        "event_type": "library_frozen",
                        "env_id": "E1",
                        "hash": "stable-library-hash",
                    }
                ),
                *[
                    json.dumps(
                        {
                            "event_type": "trial_started",
                            "phase": "evaluation",
                            "task_id": f"E1-LS{family}-T{tier}",
                            "library_hash": "stable-library-hash",
                        }
                    )
                    for family in range(1, 6)
                    for tier in range(4, 7)
                ],
            ]
        )
        + "\n",
        encoding="utf-8",
    )

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


def test_oracle_integrity_accepts_only_manifest_proven_post_run_redaction(
    tmp_path: Path,
) -> None:
    import hashlib
    import json

    output_root = tmp_path / "artifacts/output"
    skill_dir = output_root / "runs/run/oracle-skill-views/E2-LS2-T6/example"
    skills_root = tmp_path / "benchmark/skills"
    canonical_path = skills_root / "example/SKILL.md"
    delivered_path = skill_dir / "SKILL.md"
    canonical_path.parent.mkdir(parents=True)
    delivered_path.parent.mkdir(parents=True)
    canonical = b'headers = {"Authorization": f"Bearer {token}"}\n'
    delivered = b'headers = {"Authorization": [REDACTED] {token}"}\n'
    canonical_path.write_bytes(canonical)
    delivered_path.write_bytes(delivered)
    relative = delivered_path.relative_to(output_root).as_posix()
    manifest = {
        "changed_files": [{
            "path": relative,
            "runtime_sha256": hashlib.sha256(canonical).hexdigest(),
            "runtime_size": len(canonical),
            "delivered_sha256": hashlib.sha256(delivered).hexdigest(),
            "delivered_size": len(delivered),
        }],
    }
    (output_root / "sanitization_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    audit_hash = COLLECTOR.projected_skill_digest(canonical)

    kwargs = {
        "skill_dir": skill_dir,
        "audit_sha256": audit_hash,
        "slug": "example",
        "skills_root": skills_root,
        "output_root": output_root,
    }
    assert COLLECTOR.sanitized_skill_matches_runtime_audit(**kwargs) is True
    assert ORACLE_VALIDATOR.sanitized_skill_matches_runtime_audit(**kwargs) is True

    manifest["changed_files"][0]["runtime_sha256"] = "0" * 64
    (output_root / "sanitization_manifest.json").write_text(
        json.dumps(manifest), encoding="utf-8"
    )
    assert COLLECTOR.sanitized_skill_matches_runtime_audit(**kwargs) is False
    assert ORACLE_VALIDATOR.sanitized_skill_matches_runtime_audit(**kwargs) is False


def test_oracle_skill_use_audit_separates_assignment_from_compliance() -> None:
    specs = {
        "E2-LS1-T5": {
            "task_index": 5,
            "primary_skill": "E2-LS1.validate",
            "required_skills": [],
        },
        "E2-LS1-T6": {
            "task_index": 6,
            "primary_skill": "E2-LS1.validate",
            "required_skills": ["E2-LS1.validate", "E2-LS5.fallback"],
        },
    }
    records = {
        "E2-LS1-T5": {"skills_actually_used": ["E2-LS1.validate"]},
        "E2-LS1-T6": {"skills_actually_used": ["E2-LS1.validate"]},
    }

    result = ORACLE_VALIDATOR.oracle_skill_use_audit(records, specs)

    assert result["task_count"] == 2
    assert result["full_use_count"] == 1
    assert result["any_use_count"] == 2
    assert result["no_use_count"] == 0
    assert result["rows"][1]["missing_expected_skill_ids"] == [
        "E2-LS5.fallback"
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


def test_matched_skill_content_separates_text_distance_from_behavior() -> None:
    learning = {
        "families": [
            {
                "model": "qwen3.7-max",
                "environment_id": "E2",
                "family_id": "E2-LS1",
                "generated_skill_count": 2,
                "learning_attempts": 5,
                "terminal_strict_passes": 2,
                "repaired_to_pass": 1,
                "best_word_jaccard": 0.2,
                "generated_verifier_marker_hits": 7,
                "oracle_verifier_marker_hits": 0,
                "generated_text": "long generated verifier-specific procedure",
                "curated_text": "short scaffold",
                "generated_concepts": ["jitter", "idempotency"],
                "curated_concepts": ["idempotency"],
            }
        ]
    }
    comparisons = []
    for task_id, outcome, strict in (
        ("E2-LS1-T5", True, False),
        ("E2-LS1-T6", False, False),
    ):
        comparisons.append(
            {
                "model": "qwen3.7-max",
                "environment_id": "E2",
                "task_id": task_id,
                "tier": int(task_id[-1]),
                "conditions": {
                    "self_generated": {"outcome": outcome, "strict": strict},
                    "exact_oracle": {
                        "outcome": outcome,
                        "strict": strict,
                        "oracle_skill_ids": ["E2-LS1.retry"],
                        "skills_actually_used": ["E2-LS1.retry"],
                    },
                    "no_skill": None,
                    "curated_all": None,
                },
            }
        )

    result = REPORT.matched_skill_content_diagnostics(learning, comparisons)

    assert len(result) == 1
    row = result[0]
    assert row["matched_tasks"] == 2
    assert row["complete_t5_t6_slice"] is False
    assert row["outcome_vectors_identical"] is True
    assert row["strict_vectors_identical"] is True
    assert row["self_outcome_passed"] == row["exact_outcome_passed"] == 1
    assert row["generated_skill_count"] == 2
    assert row["generated_verifier_marker_hits"] == 7
    assert row["generated_only_concepts"] == ["jitter"]
    assert row["exact_full_skill_use"] == row["exact_skill_use_audited"] == 2
    assert row["controls"]["no_skill"] == {
        "observed": 0,
        "outcome_passed": 0,
        "strict_passed": 0,
    }


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


def test_protocol_design_audit_proves_curated_skills_are_gap_exposed() -> None:
    result = REPORT.protocol_design_audit(
        {"tasks_root": str(ROOT / "benchmark/tasks")}
    )

    assert result["family_count"] == 30
    assert result["gap_summary_count"] == 60
    assert result["gap_summaries_explicitly_limiting_curated"] == 60
    assert result["role_counts"]["T2:enriched:learning"] == 30
    assert result["role_counts"]["T3:variant:learning"] == 30


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
            "task_slug": "model-specific-process-false-negative",
            "outcome_pass": True,
            "process_pass": False,
            "classification": "process_only_failure",
        },
        {
            **common,
            "environment_id": "E5",
            "tier": 6,
            "task_id": "E5-LS2-T6",
            "task_slug": "verified-process-false-negative",
            "outcome_pass": True,
            "process_pass": False,
            "classification": "process_only_failure",
        },
        {
            **common,
            "model": "qwen3.7-max",
            "environment_id": "E6",
            "tier": 5,
            "task_id": "E6-LS3-T5",
            "task_slug": "hidden-action-id",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
        {
            **common,
            "model": "qwen3.7-max",
            "environment_id": "E6",
            "tier": 6,
            "task_id": "E6-LS2-T6",
            "task_slug": "verified-outcome-false-negative",
            "outcome_pass": False,
            "process_pass": False,
            "classification": "outcome_and_process_failure",
        },
        {
            **common,
            "model": "qwen3.7-max",
            "environment_id": "E6",
            "tier": 6,
            "task_id": "E6-LS3-T6",
            "task_slug": "mixed-contract-and-model-gap",
            "outcome_pass": False,
            "process_pass": False,
            "classification": "outcome_and_process_failure",
        },
        {
            **common,
            "model": "sig-fable",
            "environment_id": "E6",
            "tier": 5,
            "task_id": "E6-LS1-T5",
            "task_slug": "priority-rubric-conflict",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
        {
            **common,
            "model": "sig-fable",
            "environment_id": "E6",
            "tier": 5,
            "task_id": "E6-LS2-T5",
            "task_slug": "hidden-rationale-literal",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
        {
            **common,
            "model": "qwen3.7-max",
            "environment_id": "E6",
            "tier": 5,
            "task_id": "E6-LS5-T5",
            "task_slug": "hidden-action-taxonomy",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
        {
            **common,
            "model": "qwen3.7-max",
            "environment_id": "E6",
            "tier": 5,
            "task_id": "E6-LS4-T5",
            "task_slug": "underdetermined-dst-tie-break",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
        {
            **common,
            "model": "sig-fable",
            "environment_id": "E6",
            "tier": 6,
            "task_id": "E6-LS4-T6",
            "task_slug": "invalid-schedule",
            "outcome_pass": False,
            "process_pass": True,
            "classification": "outcome_only_failure",
        },
    ]
    audit = {
        "tasks": [
            {"task_id": "E2-LS1-T5", "process_shape_sensitivity": "high"},
            {"task_id": "E2-LS3-T5", "process_shape_sensitivity": "low"},
            {"task_id": "E5-LS2-T6", "process_shape_sensitivity": "medium"},
            {"task_id": "E6-LS2-T6", "process_shape_sensitivity": "medium"},
            {"task_id": "E6-LS1-T5", "process_shape_sensitivity": "low"},
            {"task_id": "E6-LS2-T5", "process_shape_sensitivity": "low"},
            {"task_id": "E6-LS3-T6", "process_shape_sensitivity": "medium"},
            {"task_id": "E6-LS3-T5", "process_shape_sensitivity": "low"},
            {"task_id": "E6-LS4-T5", "process_shape_sensitivity": "low"},
            {"task_id": "E6-LS5-T5", "process_shape_sensitivity": "high"},
            {"task_id": "E6-LS4-T6", "process_shape_sensitivity": "low"},
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
        "E2-LS3-T5": "verified_verifier_false_negative",
        "E5-LS2-T6": "verified_verifier_false_negative",
        "E6-LS2-T6": "verified_benchmark_false_negative",
        "E6-LS1-T5": "mixed_benchmark_and_model_gap",
        "E6-LS2-T5": "verified_benchmark_false_negative",
        "E6-LS3-T5": "verified_benchmark_false_negative",
        "E6-LS3-T6": "mixed_benchmark_and_model_gap",
        "E6-LS4-T5": "invalid_or_underdetermined_task",
        "E6-LS5-T5": "verified_benchmark_false_negative",
        "E6-LS4-T6": "invalid_or_underdetermined_task",
    }


def test_failure_attribution_handles_model_specific_e6_ls5_process_false_negative() -> None:
    rows = [{
        "selected_run": True,
        "condition": "self_generated",
        "model": "sig-fable",
        "environment_id": "E6",
        "tier": 5,
        "strict_pass": False,
        "outcome_pass": True,
        "process_pass": False,
        "classification": "process_only_failure",
        "task_id": "E6-LS5-T5",
        "task_slug": "rhetorical-question-trap",
        "failed_tests": [],
    }]
    result = REPORT.failure_attribution(
        rows,
        {"tasks": [{
            "task_id": "E6-LS5-T5",
            "process_shape_sensitivity": "high",
        }]},
        {"complete": False, "failures": []},
    )
    assert result["failures"][0]["cause"] == "verified_verifier_false_negative"


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
        "conditions": {
            "self_generated": {"outcome": False},
            "exact_oracle": {"outcome": True},
        },
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
    assert "1 个逐题匹配的 self/exact 样本" in e2["current_read"]
    assert "oracle 救回 1 题、相对退化 0 题" in e2["current_read"]
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


def test_execution_attempt_audit_separates_platform_failures_from_results(
    tmp_path: Path,
) -> None:
    config_job = tmp_path / "fable-exact-E1" / "ap-config"
    config_output = config_job / "artifacts/output"
    config_output.mkdir(parents=True)
    (config_output / "metrics.json").write_text(
        json.dumps(
            {
                "status": "failed",
                "message": (
                    "learning_max_attempts > 1 requires "
                    "skill_update_source='same_agent_session'"
                ),
            }
        ),
        encoding="utf-8",
    )
    mirror_job = tmp_path / "sig-fable-e4" / "ap-mirror"
    mirror_output = mirror_job / "artifacts/output"
    exception = (
        mirror_output
        / "runs/run-1/harbor-job/run-1/E4-LS1-T1__x/exception.txt"
    )
    exception.parent.mkdir(parents=True)
    exception.write_text(
        "File has unexpected size. Mirror sync in progress?",
        encoding="utf-8",
    )
    (mirror_output / "metrics.json").write_text(
        json.dumps({"status": "failed", "message": "RuntimeError"}),
        encoding="utf-8",
    )
    evidence = {
        "runs": [
            {
                "job_id": "ap-mirror",
                "run_id": "run-1",
                "selected_run": True,
            }
        ],
        "tasks": [{"job_id": "ap-mirror", "selected_run": True}],
    }

    result = REPORT.execution_attempt_audit(tmp_path, evidence)

    assert result["failed_attempt_count"] == 2
    assert result["excluded_attempt_count"] == 1
    assert result["failed_attempts_contributing_t56"] == 1
    assert result["failure_counts"] == {
        "invalid_eval_configuration": 1,
        "package_mirror_sync": 1,
    }
    by_job = {row["job_id"]: row for row in result["failures"]}
    assert by_job["ap-config"]["contributes_t56_results"] is False
    assert by_job["ap-mirror"]["contributes_t56_results"] is True
    assert by_job["ap-mirror"]["selected_run_candidate"] is True
    assert by_job["ap-mirror"]["exception_path"].endswith("exception.txt")


def test_oracle_case_studies_use_only_the_declared_condition(tmp_path: Path) -> None:
    task_root = tmp_path / "tasks" / "oracle-path-contract"
    (task_root / "solution").mkdir(parents=True)
    (task_root / "instruction.md").write_text("task contract\n", encoding="utf-8")
    (task_root / "solution" / "solve.sh").write_text(
        "#!/bin/sh\n", encoding="utf-8"
    )
    outcome_path = tmp_path / "test_outcome.py"
    process_path = tmp_path / "test_process.py"
    outcome_path.write_text("def test_outcome(): pass\n", encoding="utf-8")
    process_path.write_text("def test_process(): pass\n", encoding="utf-8")
    common = {
        "task_id": "E2-LS1-T6",
        "task_slug": "oracle-path-contract",
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
        {
            "tasks_root": str(tmp_path / "tasks"),
            "tasks": [
                {
                    "task_id": "E2-LS1-T6",
                    "task_slug": "oracle-path-contract",
                    "outcome": {"path": str(outcome_path)},
                    "process": {"path": str(process_path)},
                }
            ],
        },
        tmp_path,
    )

    case = next(item for item in cases if item["task_id"] == "E2-LS1-T6")
    assert [row["condition"] for row in case["observations"]] == [
        "self_generated",
        "exact_oracle",
    ]
    assert case["instruction"] == "task contract\n"
    assert case["outcome_verifier"] == "def test_outcome(): pass\n"
    assert case["process_verifier"] == "def test_process(): pass\n"
    assert case["reference_solution"] == "#!/bin/sh\n"


def test_case_study_recovers_final_edits_from_trajectory(tmp_path: Path) -> None:
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(
        json.dumps(
            {
                "events": [
                    {
                        "tool_calls": [
                            {
                                "function_name": "edit",
                                "arguments": {
                                    "filePath": "/root/task/backend/services.py",
                                    "oldString": "old binding",
                                    "newString": "dynamic binding",
                                },
                            },
                            {
                                "function_name": "read",
                                "arguments": {
                                    "filePath": "/root/task/backend/services.py"
                                },
                            },
                        ]
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    edits = REPORT.trajectory_final_edits(trajectory)
    activity = REPORT.trajectory_tool_activity(trajectory)

    assert edits == [
        {
            "file_path": "/root/task/backend/services.py",
            "old": "old binding",
            "new": "dynamic binding",
        }
    ]
    assert activity["tool_counts"] == {"edit": 1, "read": 1}
    assert activity["mutation_call_count"] == 1
    assert activity["bash_commands"] == []
    assert activity["step_count"] == 0
    assert activity["terminal_completion_tokens"] is None
    assert activity["terminal_reasoning_chars"] == 0


def test_trajectory_activity_exposes_terminal_output_cap_without_tools(
    tmp_path: Path,
) -> None:
    trajectory = tmp_path / "trajectory.json"
    trajectory.write_text(
        json.dumps(
            {
                "steps": [
                    {"step_id": 1, "source": "user", "message": "task"},
                    {
                        "step_id": 2,
                        "source": "agent",
                        "reasoning_content": "x" * 47_013,
                        "metrics": {"completion_tokens": 16_384},
                        "tool_calls": [],
                    },
                ]
            }
        ),
        encoding="utf-8",
    )

    activity = REPORT.trajectory_tool_activity(trajectory)

    assert activity["step_count"] == 2
    assert activity["agent_step_count"] == 1
    assert activity["max_step_completion_tokens"] == 16_384
    assert activity["terminal_completion_tokens"] == 16_384
    assert activity["terminal_reasoning_chars"] == 47_013
    assert activity["terminal_has_tool_calls"] is False


def test_e5_ls5_reproduction_proves_provenance_keys_were_public(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "false-contradiction-different-timeframes-trap"
    artifact_root = tmp_path / "task"
    output_dir = artifact_root / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "consistency_audit.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "reason": "same context but incompatible values",
                        "provenance": {
                            "source_ids": ["source-a"],
                            "source_urls": ["https://example.test/a"],
                            "method": "schema-shaped replacement",
                        },
                    }
                ]
            }
        ),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e5_ls5_provenance_contract(
        task_root,
        [
            {
                "model": "sig-fable",
                "condition": "self_generated",
                "outcome": False,
                "process": False,
                "artifact_task_path": str(artifact_root),
                "final_edits": [
                    {
                        "new": "provenance_block(source_ids, method, limitations)",
                    }
                ],
                "trajectory_step_count": 14,
                "mutation_call_count": 4,
            }
        ],
    )

    assert result["required_keys_are_public_in_starter_pipeline"] is True
    assert result["required_keys_are_public_in_outcome_test"] is True
    model = result["models"][0]
    assert model["artifact_provenance_keys"] == [
        "method",
        "source_ids",
        "source_urls",
    ]
    assert model["artifact_has_all_required_keys"] is False
    assert model["edits_touch_load_provenance"] is False
    assert model["effective_has_all_required_keys"] is False


def test_e5_ls1_reproduction_distinguishes_unconditional_classification_rule(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "multi-dimension-filter-rank"
    qwen_task = tmp_path / "qwen"
    fable_task = tmp_path / "fable"
    for path, selected in (
        (qwen_task, ["M01", "M05", "M02", "M12", "M06"]),
        (fable_task, ["M01", "M02", "M04", "M03", "M05"]),
    ):
        (path / "output").mkdir(parents=True)
        (path / "output" / "selection.json").write_text(
            json.dumps({"selected": selected}), encoding="utf-8"
        )

    result = REPORT.reproduce_e5_ls1_skill_transfer(
        task_root,
        [
            {
                "model": "qwen3.7-max",
                "condition": "self_generated",
                "outcome": False,
                "process": True,
                "artifact_task_path": str(qwen_task),
                "used_skill_files": [
                    {
                        "content": "Core Principle: Classify before ranking."
                    }
                ],
                "trajectory_step_count": 18,
                "mutation_call_count": 4,
            },
            {
                "model": "sig-fable",
                "condition": "self_generated",
                "outcome": True,
                "process": True,
                "artifact_task_path": str(fable_task),
                "used_skill_files": [
                    {
                        "content": "Pick the variant from the output schema. Ranking variant."
                    }
                ],
                "trajectory_step_count": 13,
                "mutation_call_count": 3,
            },
        ],
    )

    assert result["required_entrypoint_is_public_in_outcome_test"] is True
    assert result["starter_pipeline_compiles"] is False
    assert result["schema_requires_only_selected"] is True
    by_model = {row["model"]: row for row in result["models"]}
    assert by_model["qwen3.7-max"]["skill_says_classify_before_ranking"] is True
    assert by_model["qwen3.7-max"]["must_exclude_selected"] == ["M12"]
    assert by_model["qwen3.7-max"]["preferred_selected_count"] == 3
    assert by_model["sig-fable"]["skill_says_pick_variant_from_schema"] is True
    assert by_model["sig-fable"]["must_exclude_selected"] == []
    assert by_model["sig-fable"]["preferred_selected_count"] == 5


def test_e3_ls5_reproduction_exposes_generator_verifier_conflict() -> None:
    task_root = ROOT / "benchmark" / "tasks" / "correct-syntax-wrong-logic-trap"

    result = REPORT.reproduce_e3_ls5_active_counts(task_root)

    assert result["generator_declared_active"] == 700
    assert result["generator_labels_1_2_3_bad"] is True
    assert result["loose_parser_active"] == 706
    assert result["strict_parser_active"] == 700
    assert result["extra_active_from_loose_parser"] == 6
    assert result["malformed_qualified_rows_under_loose_parser"] == 38
    assert result["malformed_qualified_rows_under_strict_parser"] == 0


def test_e6_ls3_reproduction_aligns_semantic_actions_by_source(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "full-thread-extract-track-followup"
    artifact_root = tmp_path / "task"
    output_dir = artifact_root / "output"
    output_dir.mkdir(parents=True)
    actions = []
    source_specs = [
        ("act_webhook_runbook", "ft01", "alice", "2026-04-13", "overdue"),
        ("act_pricing_faq", "ft02", "bob", "2026-04-15", "overdue"),
        ("act_emea_dns", "ft03", "charlie", None, "delayed"),
        ("act_customer_comms", "ft04", "diana", "2026-04-24", "completed"),
        ("act_regression", "ft05", "eli", "2026-04-27", "open"),
        ("act_docs_update", "ft06", "team", "2026-04-30", "open"),
        ("act_migration_mapping", "ft07", "alice", None, "no_update"),
        ("act_partner_qa", "ft08", "bob", "2026-04-24", "open"),
    ]
    for action_id, source_id, assignee, deadline, status in source_specs:
        actions.append({
            "id": action_id,
            "source_message_id": source_id,
            "description": action_id,
            "assignee": assignee,
            "deadline": deadline,
            "status": status,
        })
    (output_dir / "actions.json").write_text(
        json.dumps({"actions": actions}), encoding="utf-8"
    )

    result = REPORT.reproduce_e6_ls3_action_identity(
        task_root,
        [{
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "artifact_task_path": str(artifact_root),
        }],
    )

    model = result["models"][0]
    assert model["source_aligned_actions_found"] == 8
    assert model["expected_actions"] == 8
    assert model["exact_hidden_id_matches"] == 6
    assert model["core_fields_matched"] == 23
    assert model["core_fields_semantically_matched"] == 23
    assert model["core_fields_checked"] == 24
    assert {row["verifier_expected_id"] for row in model["id_mismatches"]} == {
        "act_runbook",
        "act_docs",
    }
    assert model["core_field_mismatches"] == [{
        "source_message_id": "ft06",
        "field": "status",
        "expected": "no_update",
        "actual": "open",
        "matched": False,
        "semantic_matched": False,
    }]


def test_e6_ls3_t5_reproduction_accepts_public_team_assignees(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "question-masquerading-as-action-trap"
    artifact_root = tmp_path / "task"
    output_dir = artifact_root / "output"
    output_dir.mkdir(parents=True)
    (output_dir / "actions.json").write_text(
        json.dumps({
            "actions": [
                {
                    "id": "act_q4_targets_planning",
                    "source_message_id": "q02",
                    "assignee": "product",
                    "deadline": None,
                    "status": "open",
                },
                {
                    "id": "act_northstar_call",
                    "source_message_id": "q04",
                    "assignee": "customer_success",
                    "deadline": None,
                    "status": "open",
                },
                {
                    "id": "act_notes_cleanup",
                    "source_message_id": "q06",
                    "assignee": "fatima",
                    "deadline": "2026-04-24",
                    "status": "open",
                },
            ]
        }),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e6_ls3_action_identity(
        task_root,
        [{
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "artifact_task_path": str(artifact_root),
        }],
    )

    row = result["models"][0]
    assert row["source_aligned_actions_found"] == 3
    assert row["expected_actions"] == 3
    assert row["exact_hidden_id_matches"] == 2
    assert row["core_fields_matched"] == 7
    assert row["core_fields_semantically_matched"] == 9
    assert row["core_fields_checked"] == 9
    assert row["id_mismatches"] == [{
        "source_message_id": "q02",
        "verifier_expected_id": "act_revisit_targets",
        "model_id": "act_q4_targets_planning",
    }]


def test_e4_ls3_reproduction_exposes_missing_marker_contract_conflict(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "hallucination-trap-3-missing-fields"
    artifact_root = tmp_path / "task"
    artifact_root.mkdir()
    (artifact_root / "missing_policy.py").write_text(
        'DEFAULT_MISSING_MARKER = "MISSING"\n', encoding="utf-8"
    )

    result = REPORT.reproduce_e4_ls3_missing_markers(
        task_root, artifact_root
    )

    assert result["verifier_accepted_strings"] == ["N/A", "TODO", "null"]
    assert result["instruction_example_acceptance"] == {
        "UNKNOWN": False,
        "MISSING": False,
        "empty string": False,
        "JSON null": False,
    }
    assert result["model_marker"] == "MISSING"
    assert result["model_marker_accepted"] is False
    assert result["verifier_uses_str_value_membership"] is True


def test_e4_ls2_reproduction_separates_commas_from_numeric_correctness(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "pdf-json-docx-chain"
    artifact = tmp_path / "task"
    artifact.mkdir()
    expected = json.loads(
        (task_root / "tests" / "expected_financials.json").read_text()
    )
    (artifact / "extracted.json").write_text(
        json.dumps(expected), encoding="utf-8"
    )
    (artifact / "pipeline.py").write_text(
        "extract_financials(); build_docx(JSON_OUT)\n", encoding="utf-8"
    )
    (artifact / "pdf_extract.py").write_text(
        "profit = revenue - expenses\n", encoding="utf-8"
    )
    (artifact / "docx_writer.py").write_text(
        "doc.add_table(rows=1, cols=4)\n", encoding="utf-8"
    )
    flattened = " ".join(
        item
        for quarter, values in expected.items()
        for item in [quarter, *(f"{int(value):,}" for value in values.values())]
    )
    with zipfile.ZipFile(artifact / "report.docx", "w") as archive:
        archive.writestr(
            "word/document.xml",
            f'<w:document xmlns:w="x"><w:body><w:p><w:r><w:t>{flattened}</w:t>'
            "</w:r></w:p></w:body></w:document>",
        )

    result = REPORT.reproduce_e4_ls2_docx_number_surface(
        task_root,
        [{
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "outcome": False,
            "artifact_task_path": str(artifact),
        }],
    )

    row = result["models"][0]
    assert row["json_exact_expected"] is True
    assert row["quarters_present"] == 4
    assert row["raw_integer_strings_present"] == 0
    assert row["integer_strings_present_after_comma_normalization"] == 12
    assert row["helpers_implement_profit_and_add_table"] is True
    assert result["instruction_requires_raw_unformatted_integer_strings"] is False
    assert result["outcome_verifier_uses_assert_in_str_value"] is True


def test_e4_ls4_t5_reproduction_exposes_tense_sensitive_hidden_regex(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "page-number-reference-error-trap"
    self_artifact = tmp_path / "self" / "task"
    (self_artifact.parent / "output").mkdir(parents=True)
    (self_artifact.parent / "output" / "revenue_analysis.md").write_text(
        "# Revenue Analysis\n118.3 FY2023 page 47; the stale pointer points to page 23.",
        encoding="utf-8",
    )
    exact_trajectory = tmp_path / "exact.json"
    exact_report = (
        "# Revenue Analysis\n118.3 FY2023; source page 47. "
        "The internal reference on page 23 pointed to FY2022 prior-year data."
    )
    exact_trajectory.write_text(
        json.dumps({
            "steps": [{
                "observation": {"results": [{"content": exact_report}]}
            }]
        }),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e4_ls4_t5_reference_wording(
        task_root,
        [
            {
                "model": "qwen3.7-max",
                "condition": "self_generated",
                "outcome": True,
                "artifact_task_path": str(self_artifact),
            },
            {
                "model": "qwen3.7-max",
                "condition": "exact_oracle",
                "outcome": False,
                "trajectory_path": str(exact_trajectory),
            },
        ],
    )

    self_row, exact_row = result["models"]
    assert self_row["semantic_contract_satisfied"] is True
    assert self_row["hidden_regex_matches"] is True
    assert exact_row["semantic_contract_satisfied"] is True
    assert exact_row["hidden_regex_matches"] is False


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
        "concept_dictionary_size": len(REPORT.CONCEPT_PATTERNS),
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


def test_runtime_progress_separates_ap_state_from_scientific_coverage() -> None:
    coverage = [
        {
            "model": model,
            "condition": condition,
            "environment_id": f"E{index}",
            "complete": model == "sig-fable"
            and condition == "exact_oracle"
            and index == 2,
            "observed": (
                15
                if model == "sig-fable"
                and condition == "exact_oracle"
                and index == 2
                else 0
            ),
        }
        for model in REPORT.MODELS
        for condition in REPORT.CONDITIONS
        for index in range(1, 7)
    ]
    inventory = {
        "updated_at_utc": "2026-07-22T21:00:00Z",
        "jobs": [
            {
                "label": "fable-exact-oracle-v1-16-E1",
                "job_id": "job-exact-e1",
                "group_id": "group-exact",
                "status": "Running",
                "export_state": "not_started",
                "created_at": "2026-07-22T20:00:00Z",
            },
            {
                "label": "qwen37max-e1-repair-v1-15",
                "job_id": "job-qwen-e1",
                "group_id": None,
                "status": "Succeeded",
                "export_state": "complete",
                "created_at": "2026-07-22T19:00:00Z",
            },
        ],
    }
    matrix_state = {
        "updated_at_utc": "2026-07-22T21:00:01Z",
        "stages": {
            "fable_exact_oracle": {
                "status": "submitted",
                "group_id": "group-exact",
                "registered_with_evidence_watcher": True,
                "failed_groups": [{"group_id": "group-old"}],
            }
        },
    }

    result = REPORT.runtime_progress_analysis(
        coverage, inventory, matrix_state
    )

    assert result["complete_cells"] == 1
    assert result["total_cells"] == 48
    assert result["active_job_count"] == 1
    exact = next(
        row for row in result["stages"] if row["stage"] == "fable_exact_oracle"
    )
    assert exact["job_statuses"] == {"Running": 1}
    assert exact["complete_cells"] == 1
    assert exact["observed_tasks"] == 15
    assert exact["failed_group_count"] == 1
    pending = next(
        row for row in result["stages"] if row["stage"] == "qwen_exact_oracle"
    )
    assert pending["group_id"] is None
    assert pending["job_statuses"] == {}
    qwen_repair = next(
        row for row in result["repairs"] if row["model"] == "qwen3.7-max"
    )
    assert qwen_repair["job_id"] == "job-qwen-e1"
    assert qwen_repair["export_state"] == "complete"


def test_measurement_validity_separates_history_from_on_task_requirements() -> None:
    derivability = {
        "records": [
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS1-T5",
                "concept": "a",
                "in_t1_t3_evidence": True,
                "in_generated_skill": True,
            },
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS2-T5",
                "concept": "a",
                "in_t1_t3_evidence": True,
                "in_generated_skill": True,
            },
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS2-T5",
                "concept": "b",
                "in_t1_t3_evidence": False,
                "in_generated_skill": False,
            },
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS3-T5",
                "concept": "b",
                "in_t1_t3_evidence": False,
                "in_generated_skill": False,
            },
        ]
    }
    oracle_scope = {
        "rows": [
            {
                "task_id": "E1-LS1-T5",
                "environment_id": "E1",
                "tier": 5,
                "task_slug": "history",
                "task_concepts": ["a"],
                "instruction_concepts": ["a"],
                "oracle_concepts": ["a"],
            },
            {
                "task_id": "E1-LS2-T5",
                "environment_id": "E1",
                "tier": 5,
                "task_slug": "mixed",
                "task_concepts": ["a", "b"],
                "instruction_concepts": ["a", "b"],
                "oracle_concepts": ["a"],
            },
            {
                "task_id": "E1-LS3-T5",
                "environment_id": "E1",
                "tier": 5,
                "task_slug": "on-task",
                "task_concepts": ["b"],
                "instruction_concepts": ["b"],
                "oracle_concepts": [],
            },
            {
                "task_id": "E1-LS4-T5",
                "environment_id": "E1",
                "tier": 5,
                "task_slug": "unclassified",
                "task_concepts": [],
                "instruction_concepts": [],
                "oracle_concepts": [],
            },
            {
                "task_id": "E1-LS5-T5",
                "environment_id": "E1",
                "tier": 5,
                "task_slug": "missing-learning",
                "task_concepts": ["a"],
                "instruction_concepts": ["a"],
                "oracle_concepts": ["a"],
            },
        ]
    }

    result = REPORT.measurement_validity_analysis(
        derivability, oracle_scope
    )
    qwen = {
        row["task_id"]: row
        for row in result["records"]
        if row["model"] == "qwen3.7-max"
    }

    assert qwen["E1-LS1-T5"]["category"] == "history_supported"
    assert qwen["E1-LS2-T5"]["category"] == "mixed_history_and_on_task"
    assert qwen["E1-LS3-T5"]["category"] == "on_task_only"
    assert qwen["E1-LS4-T5"]["category"] == (
        "unclassified_no_controlled_concept"
    )
    assert qwen["E1-LS5-T5"]["category"] == "missing_learning_evidence"
    summary = next(
        row for row in result["summaries"] if row["model"] == "qwen3.7-max"
    )
    assert summary["task_count"] == 5
    assert summary["controlled_task_count"] == 4
    assert summary["eligible_for_causal_skill_claim"] == 2
    assert summary["oracle_all_concepts"] == 2
    assert summary["generated_all_concepts"] == 1


def test_validity_stratified_effects_do_not_mix_on_task_only_tasks() -> None:
    def condition(outcome: bool) -> dict:
        return {"outcome": outcome, "strict": outcome, "process": outcome}

    comparisons = []
    for task_id, self_outcome, no_skill_outcome in (
        ("E1-LS1-T5", True, False),
        ("E1-LS2-T5", True, True),
    ):
        conditions = {
            "self_generated": condition(self_outcome),
            "exact_oracle": condition(True),
            "no_skill": condition(no_skill_outcome),
            "curated_all": condition(True),
        }
        comparisons.append(
            {
                "model": "qwen3.7-max",
                "task_id": task_id,
                "tier": 5,
                "conditions": conditions,
                "causal": REPORT.causal_diagnosis(conditions),
            }
        )
    validity = {
        "records": [
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS1-T5",
                "category": "history_supported",
            },
            {
                "model": "qwen3.7-max",
                "task_id": "E1-LS2-T5",
                "category": "on_task_only",
            },
        ]
    }

    rows = REPORT.validity_stratified_effects(comparisons, validity)
    history = next(
        row
        for row in rows
        if row["model"] == "qwen3.7-max"
        and row["validity_category"] == "history_supported"
        and row["treatment"] == "self_generated"
        and row["reference"] == "no_skill"
    )
    on_task = next(
        row
        for row in rows
        if row["model"] == "qwen3.7-max"
        and row["validity_category"] == "on_task_only"
        and row["treatment"] == "self_generated"
        and row["reference"] == "no_skill"
    )

    assert history["n"] == 1
    assert history["delta"] == 1.0
    assert history["rescued"] == 1
    assert history["complete_four_conditions"] == 1
    assert on_task["n"] == 1
    assert on_task["delta"] == 0.0
    assert on_task["complete_causal_category_counts"] == {"low_skill_demand": 1}


def test_expanded_concept_screen_uses_instruction_semantics() -> None:
    samples = {
        "business-impact prioritization": (
            "Triage by business impact rather than emotional tone."
        ),
        "multi-sheet formula preservation": (
            "Read all sheets and preserve computed formula values."
        ),
        "citation authenticity and support": (
            "Audit citation authenticity and claim support."
        ),
        "semantic null distinctions": (
            "Exclude null/offline readings and keep actual zero-degree readings."
        ),
        "dynamic pagination termination": (
            "The API metadata changes mid-run, so rechecks metadata_or_has_more."
        ),
        "systemic root-cause repair": (
            "Trace the actual root cause instead of a one-off special case."
        ),
    }

    for concept, text in samples.items():
        assert concept in REPORT.detected_concepts(text)


def test_e4_ls4_reproduction_distinguishes_literals_from_source_semantics(
    tmp_path: Path,
) -> None:
    task_root = tmp_path / "task"
    environment = task_root / "environment"
    environment.mkdir(parents=True)
    (environment / "policy_v2.md").write_text(
        "Core hours: 10 AM – 4 PM. Co-working stipend: $150 per month.\n",
        encoding="utf-8",
    )
    trajectory = tmp_path / "trajectory.json"
    report = """# Policy History Analysis
## v1 -> v2
- eligibility changed to 60 days
- work hours changed to 10 AM – 4 PM
- equipment changed to $800
- added quarterly security briefings
- co-working stipend is $150 per month
## v2 -> v3
- effective date changed
## Rollbacks
- eligibility rolled back
## Net v1 -> v3 changes
- co-working stipend remains
"""
    trajectory.write_text(
        json.dumps({"steps": [{"observation": {"content": report}}]}),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e4_ls4_literal_surface(
        task_root,
        [{
            "model": "sig-fable",
            "condition": "exact_oracle",
            "trajectory_path": str(trajectory),
        }],
    )

    assert result["source_policy_uses_en_dash_core_hours"] is True
    assert result["source_policy_uses_per_month_stipend"] is True
    row = result["models"][0]
    assert row["verifier_literal_hit_count"] == 3
    assert row["hidden_literal_check_passes"] is False
    assert row["source_normalized_semantic_hit_count"] == 5
    assert row["source_normalized_check_passes"] is True
    assert row["required_sections_present"] is True


def test_e5_ls3_t5_reproduction_exposes_unidentifiable_fake_invalid_boundary(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "fake-real-mixed-citations"
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    packet = json.loads(
        (task_root / "environment" / "citation_packet.json").read_text()
    )
    (artifact / "output" / "citation_audit.json").write_text(
        json.dumps(
            {
                "results": [
                    {
                        "citation_id": row["citation_id"],
                        "label": "invalid"
                        if row["citation_id"] in {"R08", "R09", "R10", "R13"}
                        else "valid",
                    }
                    for row in packet
                ]
            }
        ),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e5_ls3_t5_label_identifiability(
        task_root,
        [
            {
                "model": "qwen3.7-max",
                "condition": "self_generated",
                "artifact_task_path": str(artifact),
            }
        ],
    )

    assert result["absent_source_expected_label_counts"] == {
        "fake": 3,
        "invalid": 1,
    }
    assert result["same_source_id_with_conflicting_hidden_labels"] == [
        {
            "source_id": "MED_NATURE_TABLE3_DEPLOYMENT",
            "citation_ids": ["R09", "R13"],
            "expected_labels": ["fake", "invalid"],
        }
    ]
    assert result["models"][0]["missing_registry_labels_are_consistent"] is True
    assert result["article_claim_label_word_leak"]["R10"] == ["fake"]
    assert result["article_claim_label_word_leak"]["R13"] == ["invalid"]


def test_e5_ls3_t6_reproduction_separates_semantics_from_token_contract(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "full-citation-audit"
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    ground_truth = json.loads((task_root / "tests" / "ground_truth.json").read_text())
    results = [
        {
            "citation_id": citation_id,
            "label": "valid" if citation_id == "S02" else expected,
            "reason": (
                "Water intake is unrelated to AI ethics; topic mismatch."
                if citation_id == "M02"
                else "evidence-backed reason"
            ),
        }
        for citation_id, expected in ground_truth["labels"].items()
    ]
    (artifact / "output" / "citation_audit.json").write_text(
        json.dumps({"results": results}), encoding="utf-8"
    )
    (artifact / "citation_policy.py").write_text(
        "if source.get('source_type') == 'fake_citation' or not "
        "source.get('authentic', True): return {'label': 'fake'}\n",
        encoding="utf-8",
    )

    result = REPORT.reproduce_e5_ls3_t6_semantic_audit(
        task_root,
        [
            {
                "model": "qwen3.7-max",
                "condition": "self_generated",
                "artifact_task_path": str(artifact),
            }
        ],
    )

    assert result["s02_claim_preserves_image_scope"] is True
    assert result["s02_claim_makes_universal_or_all_settings_claim"] is False
    row = result["models"][0]
    assert row["exact_label_count"] == 14
    assert row["label_mismatches"] == [
        {
            "citation_id": "S02",
            "expected": "selective",
            "actual": "valid",
        }
    ]
    assert row["m02_official_reason_word_match"] is False
    assert row["m02_semantic_topic_mismatch_match"] is True
    assert row["policy_checks_manifest_authenticity_semantics"] is True
    assert row["policy_satisfies_hidden_authenticity_token_shape"] is False


def test_e5_ls4_reproduction_accepts_theme_identity_and_word_family(
    tmp_path: Path,
) -> None:
    task_root = ROOT / "benchmark" / "tasks" / "hierarchical-series-summarization"
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    article_summaries = [
        {
            "text": text,
            "selected_sections": [section_id],
            "word_count": len(text.split()),
        }
        for section_id, text in (
            ("a1_method_validation", "Validated diagnostic method."),
            ("a2_method_governance", "Governance method."),
            ("a3_method_monitoring", "Monitoring method."),
            ("a4_application_retina", "Retinal application."),
            ("a5_application_skin", "Skin application."),
        )
    ]
    group_summaries = [
        {
            "group_id": "application",
            "text": "Retinal and skin application.",
            "selected_sections": ["a4_application_retina", "a5_application_skin"],
            "word_count": 4,
        },
        {
            "group_id": "method",
            "text": "Validated diagnostic method with governance and monitoring.",
            "selected_sections": [
                "a1_method_validation",
                "a2_method_governance",
                "a3_method_monitoring",
            ],
            "word_count": 7,
        },
    ]
    overall = {
        "text": "Validated diagnostic method, governance, retinal skin application.",
        "selected_sections": [
            "a1_method_validation",
            "a2_method_governance",
            "a3_method_monitoring",
            "a4_application_retina",
            "a5_application_skin",
        ],
        "word_count": 7,
    }
    (artifact / "output" / "summary.json").write_text(
        json.dumps(
            {
                "article_summaries": article_summaries,
                "group_summaries": group_summaries,
                "overall_summary": overall,
            }
        ),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e5_ls4_hierarchy_semantics(
        task_root,
        [
            {
                "model": "qwen3.7-max",
                "condition": "self_generated",
                "artifact_task_path": str(artifact),
            }
        ],
    )

    assert result["instruction_explicitly_prescribes_method_first_group_order"] is False
    assert result["schema_requires_group_theme_or_id"] is False
    row = result["models"][0]
    assert row["article_summary_count"] == 5
    assert row["group_summary_count"] == 2
    assert row["must_select_complete"] is True
    assert row["exact_required_terms_complete"] is False
    assert row["source_normalized_required_terms_complete"] is True
    assert row["semantic_group_set_complete"] is True
    assert row["hidden_positional_group_check_passes"] is False


def test_e6_ls2_reproduction_accepts_explicit_semantic_equivalents(
    tmp_path: Path,
) -> None:
    task_root = tmp_path / "task"
    tests_root = task_root / "tests"
    tests_root.mkdir(parents=True)
    ground_truth = {
        "expected_reply_ids": ["combo_02", "combo_03"],
        "expected_ack_ids": ["combo_05"],
        "expected_ignore_ids": ["combo_08"],
        "required_terms": {
            "combo_03": [
                ["MVP"],
                ["six-week", "six week"],
                ["not promise", "would not promise"],
            ]
        },
        "expected_cc": {"combo_03": ["stakeholder@example.com"]},
        "forbidden_phrases": ["sure, we can"],
    }
    (tests_root / "ground_truth.json").write_text(
        json.dumps(ground_truth), encoding="utf-8"
    )
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    output = {
        "replies": [
            {
                "email_id": "combo_02",
                "cc": [],
                "body": "Plan A has the shorter timeline.",
                "rationale": "Answer grounded in thread_history and thread_notes.",
            },
            {
                "email_id": "combo_03",
                "cc": ["stakeholder@example.com"],
                "body": "We cannot commit to the full build; use MVP over six-week delivery.",
                "rationale": "Used engineering context.",
            },
        ],
        "acknowledgements": [{"email_id": "combo_05"}],
        "ignored": [{"email_id": "combo_08"}],
    }
    (artifact / "output" / "replies.json").write_text(
        json.dumps(output), encoding="utf-8"
    )
    (artifact / "reply_policy.py").write_text(
        "def choose_action(message): return 'reply'\n", encoding="utf-8"
    )
    (artifact / "context_loader.py").write_text(
        "def load_thread_history(): return {}\n", encoding="utf-8"
    )

    result = REPORT.reproduce_e6_ls2_semantic_phrasing(
        task_root,
        [{
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "artifact_task_path": str(artifact),
        }],
    )

    row = result["models"][0]
    assert row["reply_ids_exact"] is True
    assert row["ack_ids_exact"] is True
    assert row["ignore_ids_exact"] is True
    assert row["expected_cc_preserved"] is True
    assert row["combo_03_official_refusal_phrase_match"] is False
    assert row["combo_03_semantic_refusal_match"] is True
    assert row["combo_03_official_required_groups"] == 2
    assert row["combo_03_semantic_required_groups"] == 3
    assert row["combo_02_official_thread_context_match"] is False
    assert row["combo_02_semantic_thread_evidence_match"] is True
    assert row["literal_triage_marker_in_policy_source"] is False


def test_e6_ls1_reproduction_separates_hidden_literals_from_public_contract(
    tmp_path: Path,
) -> None:
    task_root = tmp_path / "task"
    tests_root = task_root / "tests"
    mail_root = task_root / "environment" / "mail"
    mail_root.mkdir(parents=True)
    tests_root.mkdir(parents=True)
    (task_root / "instruction.md").write_text(
        "For P0 items only, draft immediate replies with an ETA. Include only "
        "messages that truly need responses in response_list.\n",
        encoding="utf-8",
    )
    ground_truth = {
        "expected_priorities": {
            "checkout_incident": "P0",
            "launch_copy": "P1",
        },
        "expected_p0": ["checkout_incident"],
        "expected_response_ids": ["checkout_incident"],
        "expected_drafts": {"checkout_incident": {}},
    }
    (tests_root / "ground_truth.json").write_text(
        json.dumps(ground_truth), encoding="utf-8"
    )
    (mail_root / "messages.json").write_text(
        json.dumps({
            "messages": [
                {"id": "checkout_incident", "body": "Bridge is open."},
                {"id": "launch_copy", "body": "Please review today."},
            ]
        }),
        encoding="utf-8",
    )
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    output = {
        "items": [
            {
                "id": "checkout_incident",
                "priority": "P0",
                "reason": "Active production incident with open bridge.",
            },
            {"id": "launch_copy", "priority": "P1", "reason": "Review needed."},
        ],
        "response_list": ["checkout_incident", "launch_copy"],
        "drafts": [{
            "email_id": "checkout_incident",
            "body": "Joining inc-7421 to investigate the queue; ETA within 30 minutes.",
        }],
    }
    (artifact / "output" / "triage.json").write_text(
        json.dumps(output), encoding="utf-8"
    )

    result = REPORT.reproduce_e6_ls1_hidden_reply_contract(
        task_root,
        [{
            "model": "sig-fable",
            "condition": "self_generated",
            "artifact_task_path": str(artifact),
        }],
    )

    assert result[
        "hidden_10_30_appears_in_public_instruction_or_environment"
    ] is False
    row = result["models"][0]
    assert row["all_priorities_exact"] is True
    assert row["p0_set_exact"] is True
    assert row["draft_ids_exact"] is True
    assert row["response_list_exact_hidden_set"] is False
    assert row["extra_response_ids_with_explicit_requests"] == ["launch_copy"]
    assert row["checkout_has_semantic_eta"] is True
    assert row["checkout_has_hidden_10_30_literal"] is False
    assert row["checkout_reason_has_hidden_immediate_literal"] is False
    assert row["checkout_reason_has_semantic_incident_evidence"] is True


def test_e6_ls4_t5_reproduction_proves_dst_tie_break_is_underdetermined(
    tmp_path: Path,
) -> None:
    task_root = tmp_path / "task"
    environment = task_root / "environment"
    participants_dir = environment / "calendar"
    tests_dir = task_root / "tests"
    participants_dir.mkdir(parents=True)
    tests_dir.mkdir(parents=True)
    (task_root / "instruction.md").write_text(
        "Schedule a 60-minute meeting on March 15 with real IANA time zones. "
        "Generated slot ids are allowed.\n",
        encoding="utf-8",
    )
    (environment / "scheduling_request.json").write_text(
        json.dumps({
            "duration_minutes": 60,
            "date_range": ["2023-03-15", "2023-03-15"],
        }),
        encoding="utf-8",
    )
    (participants_dir / "participants.json").write_text(
        json.dumps({
            "participants": [
                {
                    "id": "ny",
                    "timezone": "America/New_York",
                    "work_hours": {"start": "09:00", "end": "17:00"},
                    "preferences": {},
                    "events": [],
                },
                {
                    "id": "ldn",
                    "timezone": "Europe/London",
                    "work_hours": {"start": "09:00", "end": "17:00"},
                    "preferences": {},
                    "events": [],
                },
            ]
        }),
        encoding="utf-8",
    )
    (tests_dir / "ground_truth.json").write_text(
        json.dumps({
            "expected_ranked_slot_ids": ["dst_safe"],
            "required_start_utc": ["2023-03-15T14:00:00Z"],
        }),
        encoding="utf-8",
    )
    artifact = tmp_path / "artifact"
    (artifact / "output").mkdir(parents=True)
    (artifact / "output" / "schedule.json").write_text(
        json.dumps({
            "recommendations": [
                {
                    "slot_id": "generated_13",
                    "start_utc": "2023-03-15T13:00:00Z",
                    "end_utc": "2023-03-15T14:00:00Z",
                    "score": 2,
                    "soft_preferences_met": 0,
                    "local_times": ["09:00 EDT", "13:00 GMT"],
                    "reasons": ["4 hours offset"],
                },
                {
                    "slot_id": "generated_14",
                    "start_utc": "2023-03-15T14:00:00Z",
                    "end_utc": "2023-03-15T15:00:00Z",
                    "score": 2,
                    "soft_preferences_met": 0,
                    "local_times": ["10:00 EDT", "14:00 GMT"],
                    "reasons": ["4 hours offset"],
                },
            ],
            "scheduled_meetings": [],
        }),
        encoding="utf-8",
    )

    result = REPORT.reproduce_e6_ls4_t5_tie_break(
        task_root,
        [{
            "model": "qwen3.7-max",
            "condition": "self_generated",
            "artifact_task_path": str(artifact),
        }],
    )

    assert result["valid_hourly_starts"] == [
        "2023-03-15T13:00:00Z",
        "2023-03-15T14:00:00Z",
        "2023-03-15T15:00:00Z",
        "2023-03-15T16:00:00Z",
    ]
    assert result["equal_hourly_option_count"] == 4
    assert result["public_input_has_soft_preferences"] is False
    assert result["public_input_has_calendar_events"] is False
    assert result["hidden_slot_ids_appear_in_public_surface"] is False
    row = result["models"][0]
    assert row["includes_hidden_required_start"] is True
    assert row["uses_hidden_slot_id"] is False
    assert row["all_scores_equal_two"] is True
    assert row["all_soft_counts_zero"] is True
    assert row["contains_edt_gmt_four_hour_evidence"] is True


def test_pearson_correlation_handles_signal_and_constant() -> None:
    assert REPORT.pearson_correlation([0, 1, 2], [0, 1, 2]) == 1.0
    assert REPORT.pearson_correlation([1, 1, 1], [0, 1, 2]) is None
    assert REPORT.pearson_correlation([0], [1]) is None


def test_learning_transfer_diagnostics_groups_family_outcomes() -> None:
    learning = {
        "families": [
            {
                "model": "qwen3.7-max",
                "family_id": "E1-LS1",
                "terminal_strict_passes": 3,
                "learning_attempts": 4,
                "repaired_to_pass": 1,
                "best_word_jaccard": 0.5,
            },
            {
                "model": "qwen3.7-max",
                "family_id": "E1-LS2",
                "terminal_strict_passes": 1,
                "learning_attempts": 7,
                "repaired_to_pass": 0,
                "best_word_jaccard": 0.2,
            },
        ]
    }
    comparisons = []
    for family_id, t5, t6 in (
        ("E1-LS1", True, True),
        ("E1-LS2", False, False),
    ):
        for tier, outcome in ((5, t5), (6, t6)):
            comparisons.append(
                {
                    "model": "qwen3.7-max",
                    "task_id": f"{family_id}-T{tier}",
                    "tier": tier,
                    "conditions": {"self_generated": {"outcome": outcome}},
                }
            )
    measurement_validity = {
        "records": [
            {
                "model": "qwen3.7-max",
                "task_id": f"{family_id}-T{tier}",
                "generated_coverage": coverage,
            }
            for family_id, coverage in (("E1-LS1", "all"), ("E1-LS2", "none"))
            for tier in (5, 6)
        ]
    }

    result = REPORT.learning_transfer_diagnostics(
        learning, comparisons, measurement_validity
    )
    qwen = next(
        row for row in result["summaries"] if row["model"] == "qwen3.7-max"
    )

    assert qwen["families"] == 2
    by_pass = {
        row["terminal_strict_passes"]: row
        for row in qwen["by_terminal_strict_passes"]
    }
    assert by_pass[3]["combined_passed"] == 2
    assert by_pass[1]["combined_passed"] == 0
    by_coverage = {
        row["generated_coverage"]: row
        for row in qwen["by_generated_concept_coverage"]
    }
    assert by_coverage["all"]["outcome_passed"] == 2
    assert by_coverage["none"]["outcome_passed"] == 0
    assert qwen["correlations"]["terminal_passes_vs_t6"] == 1.0
