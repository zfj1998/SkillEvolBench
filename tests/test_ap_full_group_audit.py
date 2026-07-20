from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
import yaml

from scripts.ap.audit_full_group import (
    ALL_REFLECTION_STATUSES,
    EXPECTED_BASELINE,
    EXPECTED_DATASET,
    EXPECTED_ENVIRONMENTS,
    EXPECTED_ORDER_SEED,
    EXPECTED_SPLIT,
    TASK_ROLES,
    TRANSITION_KEYS,
    audit_full_group,
    main,
)
from scripts.ap.compose_standalone_full import (
    COMPOSITION_MODE,
    CompositionError,
    compose_standalone_full,
)
from skillevolbench.opencode_continuity import opencode_synthetic_continue


BENCHMARK_REVISION = "a" * 40
AGENTHUB_REVISION = "b" * 40
SOURCE_ARCHIVE_SHA256 = "c" * 64
BENCHMARK_HASH = "d" * 64
FROZEN_LIBRARY_HASH = "e" * 64
HARBOR_REVISION = "1" * 40
MODEL = "fixture-model"
SIGNED_URL_MARKER = "must-never-appear-in-audit-output"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _task_order(environment_id: str) -> list[str]:
    return [
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in range(1, 4)
    ] + [
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, 6)
        for tier in range(4, 7)
    ]


def _reward() -> dict[str, float]:
    return {
        "total_score": 100.0,
        "max_score": 100.0,
        "normalized_score": 1.0,
        "outcome_passed": 1.0,
        "process_passed": 1.0,
    }


def _export_message(
    *,
    session_id: str,
    message_id: str,
    role: str,
    text: str,
    parent_id: str | None = None,
) -> dict[str, object]:
    info: dict[str, object] = {
        "id": message_id,
        "role": role,
        "sessionID": session_id,
    }
    if parent_id is not None:
        info["parentID"] = parent_id
    return {
        "info": info,
        "parts": [
            {
                "type": "text",
                "text": text,
                "messageID": message_id,
                "sessionID": session_id,
            }
        ],
    }


def _reflection_result(audit: Path, task_id: str) -> dict[str, object]:
    session_id = f"session-{task_id}"
    prompt = audit / "self_reflection_prompt.md"
    solve_trajectory = audit / "trajectory.solve.json"
    full_trajectory = audit / "trajectory.full.json"
    solve_export = audit / "opencode.session.solve.json"
    full_export = audit / "opencode.session.full.json"
    prompt_text = "reflect on the verified outcome\n"
    prompt.write_text(prompt_text, encoding="utf-8")
    solve_steps = [
        {"step_id": 1, "source": "user", "message": "solve prompt"},
        {"step_id": 2, "source": "agent", "message": "solve answer"},
    ]
    trajectory_base = {
        "schema_version": "ATIF-v1.7",
        "session_id": session_id,
        "agent": {"name": "opencode", "version": "1.18.3"},
        "final_metrics": {},
    }
    _write_json(solve_trajectory, {**trajectory_base, "steps": solve_steps})
    _write_json(
        full_trajectory,
        {
            **trajectory_base,
            "steps": [
                *solve_steps,
                {"step_id": 3, "source": "user", "message": prompt_text},
                {
                    "step_id": 4,
                    "source": "agent",
                    "message": "reflection answer",
                },
            ],
        },
    )
    solve_messages = [
        _export_message(
            session_id=session_id,
            message_id="solve-user",
            role="user",
            text="solve prompt",
        ),
        _export_message(
            session_id=session_id,
            message_id="solve-assistant",
            role="assistant",
            text="solve answer",
            parent_id="solve-user",
        ),
    ]
    _write_json(
        solve_export,
        {"info": {"id": session_id}, "messages": solve_messages},
    )
    _write_json(
        full_export,
        {
            "info": {"id": session_id},
            "messages": [
                *solve_messages,
                _export_message(
                    session_id=session_id,
                    message_id="reflection-user",
                    role="user",
                    text=prompt_text,
                    parent_id="solve-assistant",
                ),
                _export_message(
                    session_id=session_id,
                    message_id="reflection-assistant",
                    role="assistant",
                    text="reflection answer",
                    parent_id="reflection-user",
                ),
            ],
        },
    )
    (audit / "opencode.solve.jsonl").write_text(
        json.dumps({"sessionID": session_id}) + "\n",
        encoding="utf-8",
    )
    (audit / "opencode.reflection.jsonl").write_text(
        json.dumps({"sessionID": session_id}) + "\n",
        encoding="utf-8",
    )
    _write_json(audit / "self_reflection_feedback.json", {"task_id": task_id})
    _write_json(audit / "official-verifier" / "reward.json", _reward())
    workspace_hash = "3" * 64
    return {
        "status": "noop",
        "task_id": task_id,
        "mode": "induction",
        "session_id": session_id,
        "solve_session_id": session_id,
        "reflection_session_id": session_id,
        "same_session_verified": True,
        "patch_id": None,
        "reason": "no_change_needed",
        "prompt_path": "/safe/self_reflection_prompt.md",
        "feedback_path": "/safe/self_reflection_feedback.json",
        "candidate_path": None,
        "solve_trajectory_path": "/safe/trajectory.solve.json",
        "full_session_trajectory_path": "/safe/trajectory.full.json",
        "solve_session_export_path": "/safe/opencode.session.solve.json",
        "full_session_export_path": "/safe/opencode.session.full.json",
        "prompt_sha256": _sha256(prompt),
        "solve_trajectory_sha256": _sha256(solve_trajectory),
        "full_session_trajectory_sha256": _sha256(full_trajectory),
        "solve_session_export_sha256": _sha256(solve_export),
        "full_session_export_sha256": _sha256(full_export),
        "task_workspace_hash_before": workspace_hash,
        "task_workspace_hash_after": workspace_hash,
        "trajectory_prefix_verified": True,
        "export_prefix_verified": True,
    }


def _reflection_transfer(environment_id: str) -> dict[str, object]:
    pairs = []
    for family in range(1, 6):
        for tier in range(1, 4):
            source = f"{environment_id}-LS{family}-T{tier}"
            pairs.append(
                {
                    "family_id": f"{environment_id}-LS{family}",
                    "source_task_id": source,
                    "next_task_id": f"{environment_id}-LS{family}-T{tier + 1}",
                    "reflection_status": "noop",
                    "source_passed": True,
                    "next_passed": True,
                    "transition": "success_to_success",
                }
            )
    by_status = {
        status: {
            "n_pairs": 15 if status == "noop" else 0,
            "fail_to_success_count": 0,
            "fail_to_fail_count": 0,
            "success_to_success_count": 15 if status == "noop" else 0,
            "success_to_fail_count": 0,
            "failure_recovery_rate": None,
            "success_regression_rate": 0.0 if status == "noop" else None,
        }
        for status in ALL_REFLECTION_STATUSES
    }
    return {
        "n_pairs": 15,
        "fail_to_success_count": 0,
        "fail_to_fail_count": 0,
        "success_to_success_count": 15,
        "success_to_fail_count": 0,
        "failure_recovery_rate": None,
        "success_regression_rate": 0.0,
        "by_reflection_status": by_status,
        "pairs": pairs,
    }


def _revision_safety() -> dict[str, object]:
    return {
        "n_proposed": 0,
        "n_applied": 0,
        "n_rejected": 0,
        "n_rollbacks": 0,
        "n_no_change": 15,
        "n_cross_task_revision_pairs": 0,
        **{key: 0 for key in TRANSITION_KEYS},
    }


def _metrics(environment_id: str, run_id: str) -> dict[str, object]:
    return {
        "task_score": 1.0,
        "passed": True,
        "status": "completed",
        "scoreable": True,
        "canonical": True,
        "execution_scope": "environment",
        "environment_id": environment_id,
        "family_smoke_id": None,
        "run_id": run_id,
        "baseline_name": EXPECTED_BASELINE,
        "evaluation_sr": 1.0,
        "learning_sr": 1.0,
        "n_primary_trials": 30,
        "expected_primary_trials": 30,
        "n_replay_trials": 0,
        "expected_replay_trials": 0,
        "n_shadow_trials": 0,
        "expected_shadow_trials": 0,
        "n_verifier_backed_trials": 30,
        "expected_verifier_backed_trials": 30,
        "reflection_enabled": True,
        "n_reflection_expected": 15,
        "n_reflection_terminal": 15,
        "n_reflection_attempted": 15,
        "n_reflection_completed": 0,
        "n_reflection_noop": 15,
        "n_reflection_rejected": 0,
        "n_same_session_verified": 15,
    }


def _make_environment(output: Path, environment_id: str) -> dict[str, object]:
    run_id = f"run-{environment_id.lower()}"
    run = output / "runs" / run_id
    task_order = _task_order(environment_id)
    metrics = _metrics(environment_id, run_id)

    _write_json(
        output / "dataset_episode.json",
        {
            "schema_version": "1.0",
            "dataset": EXPECTED_DATASET,
            "split": EXPECTED_SPLIT,
            "instance_id": environment_id,
            "environment_id": environment_id,
            "benchmark_revision": BENCHMARK_REVISION,
            "source_archive_sha256": SOURCE_ARCHIVE_SHA256,
            "family_count": 5,
            "primary_task_count": 30,
            "roles": [f"T{i}" for i in range(1, 7)],
            "scoreable_unit": "complete_environment_episode",
        },
    )
    _write_json(
        output / "ap_run_manifest.json",
        {
            "schema_version": "1.0",
            "benchmark_revision": BENCHMARK_REVISION,
            "canonical": True,
            "execution_scope": "environment",
            "environment_id": environment_id,
            "family_smoke_id": None,
            "smoke_max_tasks": None,
            "baseline_name": EXPECTED_BASELINE,
            "strategy_name": "chain",
            "order_seed": EXPECTED_ORDER_SEED,
            "within_env_replay": False,
            "replay_eval": False,
            "run_id": run_id,
            "harbor_agent": "opencode",
            "model": MODEL,
        },
    )
    _write_json(output / "metrics.json", metrics)
    _write_json(
        output / "harbor_runtime.json",
        {
            "version": "0.20.0",
            "requested_git_revision": HARBOR_REVISION,
            "installed_git_commit": HARBOR_REVISION,
        },
    )
    _write_json(
        output / "agent_runtime_image.json",
        # AP can build one content-addressed runtime image per bootstrap pod.
        # Legal per-environment image IDs therefore need not be identical.
        {"id": f"sha256:{environment_id[1:] * 64}", "repo_digests": []},
    )
    model_probe = {"object": "list", "data": [{"id": MODEL}]}
    _write_json(output / "model_probe_host.json", model_probe)
    _write_json(output / "model_probe_dind.json", model_probe)
    (output / "preflight.log").write_text("sanitized preflight\n", encoding="utf-8")
    (output / "episode.log").write_text("sanitized episode\n", encoding="utf-8")

    _write_json(
        run / "config.json",
        {
            "run_id": run_id,
            "environment_id": environment_id,
            "family_smoke_id": None,
            "max_tasks": None,
            "order_seed": EXPECTED_ORDER_SEED,
        },
    )
    (run / "benchmark_hash.txt").write_text(BENCHMARK_HASH + "\n", encoding="ascii")
    _write_json(
        run / "reports" / "full_report.json",
        {
            "schema_version": "1.0",
            "run_id": run_id,
            "environment_id": environment_id,
            "baseline_name": EXPECTED_BASELINE,
            "strategy_name": "chain",
            "order_seed": EXPECTED_ORDER_SEED,
            "n_tasks_attempted": 30,
            "n_primary_trials": 30,
            "n_replay_trials": 0,
            "n_shadow_trials": 0,
            "task_success": {
                "learning_sr": 1.0,
                "evaluation_sr": 1.0,
                "n_per_role": {role: 5 for role, _phase in TASK_ROLES.values()},
            },
            "reflection": {
                "enabled": True,
                "n_terminal": 15,
                "n_attempted": 15,
                "n_completed": 0,
                "n_noop": 15,
                "n_rejected": 0,
                "n_skipped": 0,
                "n_same_session_verified": 15,
            },
            "reflection_transfer": _reflection_transfer(environment_id),
            "revision_safety": _revision_safety(),
        },
    )

    lifecycle: list[dict[str, object]] = []
    records = run / "stores" / "replay" / "records"
    harbor = run / "harbor-job" / run_id
    for index, task_id in enumerate(task_order):
        tier = int(task_id.rsplit("T", 1)[1])
        family_id = task_id.rsplit("-", 1)[0]
        role, phase = TASK_ROLES[tier]
        trial_name = f"{task_id}__trial"
        trial = harbor / trial_name
        lifecycle.append(
            {"event_type": "trial_started", "task_id": task_id, "role": role}
        )
        reflection: dict[str, object] = {}
        if index < 15:
            audit = trial / "self-reflection-audit"
            audit.mkdir(parents=True, exist_ok=True)
            reflection = _reflection_result(audit, task_id)
            _write_json(audit / "self_reflection_result.json", reflection)
            lifecycle.append({"event_type": "reflection_noop", **reflection})
        lifecycle.append(
            {
                "event_type": (
                    "trial_ended_learning" if index < 15 else "trial_ended_eval"
                ),
                "task_id": task_id,
            }
        )

        _write_json(trial / "verifier" / "reward.json", _reward())
        (trial / "verifier" / "reward.txt").write_text("1.000000\n", encoding="ascii")
        for name in ("outcome_report.json", "process_report.json", "score_report.json"):
            _write_json(trial / "verifier" / name, {})
        _write_json(
            trial / "agent" / "trajectory.solve.json",
            {"session_id": f"session-{task_id}", "steps": [{"kind": "solve"}]},
        )
        task_spec = {
            "schema_version": "1.0",
            "task_id": task_id,
            "environment_id": environment_id,
            "family_id": family_id,
            "role": role,
            "phase": phase,
        }
        spec_path = run / "runtime" / task_id / "task-spec.yaml"
        spec_path.parent.mkdir(parents=True, exist_ok=True)
        spec_path.write_text(
            yaml.safe_dump(task_spec, sort_keys=True), encoding="utf-8"
        )
        _write_json(
            records / f"{task_id}.json",
            {
                "task_id": task_id,
                "env_id": environment_id,
                "family_id": family_id,
                "task_role": role,
                "replay_mode": "primary",
                "library_hash_pre": FROZEN_LIBRARY_HASH,
                "library_hash_post": FROZEN_LIBRARY_HASH,
                "outcome": {
                    "task_id": task_id,
                    "trial_dir": f"/safe/{trial_name}",
                    "normalized_score": 1.0,
                    "reward": 1.0,
                    "verifier_passed": True,
                },
                "reflection": reflection,
            },
        )
        if index == 14:
            lifecycle.append(
                {
                    "event_type": "library_frozen",
                    "env_id": environment_id,
                    "hash": FROZEN_LIBRARY_HASH,
                }
            )
    lifecycle.extend(
        [
            {
                "event_type": "library_unfrozen",
                "env_id": environment_id,
                "n_patches_discarded": 0,
            },
            {
                "event_type": "library_swap_on_env_transition",
                "from_env": environment_id,
                "to_env": "END",
            },
            {
                "event_type": "env_transition",
                "from_env": environment_id,
                "to_env": "END",
                "library_hash": FROZEN_LIBRARY_HASH,
            },
        ]
    )
    lifecycle_path = run / "stores" / "events" / "lifecycle.jsonl"
    lifecycle_path.parent.mkdir(parents=True, exist_ok=True)
    lifecycle_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in lifecycle),
        encoding="utf-8",
    )

    delivered = output / "preflight.log"
    _write_json(
        output / "sanitization_manifest.json",
        {
            "schema_version": 1,
            "hash_algorithm": "sha256",
            "scope": "changed-utf8-regular-files",
            "excluded_mutable_paths": ["logs/main.log"],
            "changed_file_count": 1,
            "changed_files": [
                {
                    "path": "preflight.log",
                    "runtime_sha256": "f" * 64,
                    "runtime_size": delivered.stat().st_size + 1,
                    "delivered_sha256": _sha256(delivered),
                    "delivered_size": delivered.stat().st_size,
                }
            ],
        },
    )
    return metrics


def _make_group(tmp_path: Path) -> Path:
    root = tmp_path / "group-export"
    per_environment = {}
    for environment_id in EXPECTED_ENVIRONMENTS:
        output = (
            root / "jobs" / f"job-{environment_id.lower()}" / "artifacts" / "output"
        )
        per_environment[environment_id] = _make_environment(output, environment_id)
    post_job_id = "job-post-process"
    _write_json(
        root / "group.json",
        {
            "group_id": "group-fixture",
            "template": "skillevolbench",
            # Live AP group stats stores the base namespace; the immutable
            # split is verified in every dataset_episode.json below it.
            "dataset": EXPECTED_DATASET,
            "template_commit": AGENTHUB_REVISION,
            "group_post_process_job_id": post_job_id,
            "stats": {
                "total": 6,
                "finished": 6,
                "succeeded": 6,
                "failed": 0,
                "cancelled": 0,
                "pending": 0,
                "queued": 0,
                "running": 0,
                "scheduling": 0,
                "unknown": 0,
            },
        },
    )
    _write_json(
        root / "jobs" / post_job_id / "artifacts" / "output" / "metrics.json",
        {
            "task_score": 1.0,
            "evaluation_sr": 1.0,
            "passed": True,
            "status": "completed",
            "scoreable": True,
            "expected_environments": list(EXPECTED_ENVIRONMENTS),
            "missing_environments": [],
            "incomplete_environments": [],
            "n_environments": 6,
            "per_environment": per_environment,
        },
    )
    _write_json(
        root / "jobs" / post_job_id / "metrics.json",
        {
            "status": "wrapper-copy-must-not-shadow-raw",
            "scoreable": False,
        },
    )
    # This file deliberately contains a signed-link-shaped value.  The auditor
    # must never open AP download-link metadata or echo its contents.
    _write_json(
        root / "jobs" / "job-e1" / "artifacts.json",
        {"url": f"https://example.invalid/object?signature={SIGNED_URL_MARKER}"},
    )
    return root


def _reflection_fixture_paths(
    root: Path,
    task_id: str,
) -> tuple[Path, Path, Path]:
    environment_id = task_id.split("-", 1)[0]
    run_id = f"run-{environment_id.lower()}"
    run = (
        root
        / "jobs"
        / f"job-{environment_id.lower()}"
        / "artifacts"
        / "output"
        / "runs"
        / run_id
    )
    audit = run / "harbor-job" / run_id / f"{task_id}__trial" / "self-reflection-audit"
    record = run / "stores" / "replay" / "records" / f"{task_id}.json"
    lifecycle = run / "stores" / "events" / "lifecycle.jsonl"
    return audit, record, lifecycle


def _sync_reflection_fields(
    root: Path,
    task_id: str,
    fields: dict[str, object],
) -> None:
    audit, record_path, lifecycle_path = _reflection_fixture_paths(root, task_id)
    result_path = audit / "self_reflection_result.json"
    result = json.loads(result_path.read_text(encoding="utf-8"))
    result.update(fields)
    _write_json(result_path, result)

    record = json.loads(record_path.read_text(encoding="utf-8"))
    record["reflection"].update(fields)
    _write_json(record_path, record)

    rows = [
        json.loads(line)
        for line in lifecycle_path.read_text(encoding="utf-8").splitlines()
        if line
    ]
    matched = 0
    for row in rows:
        if row.get("task_id") == task_id and str(row.get("event_type", "")).startswith(
            "reflection_"
        ):
            row.update(fields)
            matched += 1
    assert matched == 1
    lifecycle_path.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )


def _export_compaction(
    session_id: str, *, auto: bool = True
) -> list[dict[str, object]]:
    compaction_id = "compaction"
    summary_id = "compaction-summary"
    continue_id = "compaction-continue"
    return [
        {
            "info": {
                "id": compaction_id,
                "role": "user",
                "sessionID": session_id,
            },
            "parts": [
                {
                    "type": "compaction",
                    "auto": auto,
                    "overflow": False,
                    "messageID": compaction_id,
                    "sessionID": session_id,
                }
            ],
        },
        {
            "info": {
                "id": summary_id,
                "role": "assistant",
                "sessionID": session_id,
                "parentID": compaction_id,
                "mode": "compaction",
                "agent": "compaction",
                "summary": True,
            },
            "parts": [
                {
                    "type": "text",
                    "text": "bounded summary",
                    "messageID": summary_id,
                    "sessionID": session_id,
                }
            ],
        },
        {
            "info": {
                "id": continue_id,
                "role": "user",
                "sessionID": session_id,
            },
            "parts": [
                {
                    "type": "text",
                    "text": opencode_synthetic_continue(overflow=False),
                    "synthetic": True,
                    "metadata": {"compaction_continue": True},
                    "messageID": continue_id,
                    "sessionID": session_id,
                }
            ],
        },
        _export_message(
            session_id=session_id,
            message_id="post-compaction-assistant",
            role="assistant",
            text="continued reflection",
            parent_id=continue_id,
        ),
    ]


def _make_standalone_exports(tmp_path: Path) -> dict[str, Path]:
    exports: dict[str, Path] = {}
    for index, environment_id in enumerate(EXPECTED_ENVIRONMENTS, start=1):
        export_root = tmp_path / "standalone" / f"job-{environment_id.lower()}"
        output = export_root / "artifacts" / "output"
        _make_environment(output, environment_id)
        metrics_path = output / "metrics.json"
        metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
        metrics.update(
            {
                "t4_transfer": index / 10,
                "fail_to_success_count": index,
                "cross_task_success_to_fail_count": 6 - index,
            }
        )
        _write_json(metrics_path, metrics)
        _write_json(
            export_root / "job.json",
            {
                "job_id": f"standalone-{environment_id.lower()}",
                "group_id": None,
                "status": "Succeeded",
                "instance_id": environment_id,
                "k8s_namespace": "megaflow-benchmark-dev",
                "template": "skillevolbench",
                "agenthub_revision": AGENTHUB_REVISION,
                "template_commit": AGENTHUB_REVISION,
            },
        )
        _write_json(
            export_root / "artifacts.json",
            {"url": f"https://example.invalid/object?signature={SIGNED_URL_MARKER}"},
        )
        exports[environment_id] = export_root
    return exports


def test_complete_group_passes_and_reports_observational_transitions(
    tmp_path: Path, capsys
) -> None:
    root = _make_group(tmp_path)

    report = audit_full_group(
        root,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
    )

    assert report.passed is True
    assert report.observed_environments == list(EXPECTED_ENVIRONMENTS)
    assert report.total_primary_trials == 180
    assert report.total_replay_trials == 0
    assert report.total_reflection_terminal == 90
    assert report.total_same_session_verified == 90
    assert report.reflection_transfer_pairs == 90
    assert report.reflection_transitions["success_to_success_count"] == 90
    assert report.revision_applied == 0
    assert report.revision_cross_task_pairs == 0
    assert report.composition_mode == "ap_group"
    assert report.aggregation_origin == "ap_group_post_process"
    assert "observational_only" in report.transition_interpretation
    assert SIGNED_URL_MARKER not in json.dumps(report.to_dict(), sort_keys=True)

    exit_code = main(
        [
            str(root),
            "--expected-benchmark-revision",
            BENCHMARK_REVISION,
            "--expected-agenthub-revision",
            AGENTHUB_REVISION,
            "--json",
        ]
    )
    captured = capsys.readouterr()
    assert exit_code == 0
    assert SIGNED_URL_MARKER not in captured.out
    assert json.loads(captured.out)["passed"] is True


def test_delivered_reflection_extra_user_fails_strict_continuity(
    tmp_path: Path,
) -> None:
    root = _make_group(tmp_path)
    task_id = "E1-LS1-T1"
    audit, _record, _lifecycle = _reflection_fixture_paths(root, task_id)
    full_path = audit / "trajectory.full.json"
    full = json.loads(full_path.read_text(encoding="utf-8"))
    full["steps"].append(
        {
            "step_id": len(full["steps"]) + 1,
            "source": "user",
            "message": "arbitrary extra user turn",
        }
    )
    _write_json(full_path, full)
    _sync_reflection_fields(
        root,
        task_id,
        {"full_session_trajectory_sha256": _sha256(full_path)},
    )

    report = audit_full_group(root)
    errors = {(item.code, item.scope) for item in report.errors}

    assert report.passed is False
    assert ("reflection_trajectory_continuity_invalid", task_id) in errors
    assert ("reflection_prefix_flags_invalid", task_id) not in errors
    assert ("reflection_runtime_delivered_hash_invalid", task_id) not in errors


def test_delivered_reflection_valid_compaction_passes_strict_continuity(
    tmp_path: Path,
) -> None:
    root = _make_group(tmp_path)
    task_id = "E1-LS1-T1"
    audit, _record, _lifecycle = _reflection_fixture_paths(root, task_id)
    full_path = audit / "opencode.session.full.json"
    full = json.loads(full_path.read_text(encoding="utf-8"))
    session_id = full["info"]["id"]
    full["messages"].extend(_export_compaction(session_id))
    _write_json(full_path, full)
    _sync_reflection_fields(
        root,
        task_id,
        {"full_session_export_sha256": _sha256(full_path)},
    )

    report = audit_full_group(root)

    assert report.passed is True


def test_delivered_reflection_compaction_near_miss_fails_strict_continuity(
    tmp_path: Path,
) -> None:
    root = _make_group(tmp_path)
    task_id = "E1-LS1-T1"
    audit, _record, _lifecycle = _reflection_fixture_paths(root, task_id)
    full_path = audit / "opencode.session.full.json"
    full = json.loads(full_path.read_text(encoding="utf-8"))
    session_id = full["info"]["id"]
    full["messages"].extend(_export_compaction(session_id, auto=False))
    _write_json(full_path, full)
    _sync_reflection_fields(
        root,
        task_id,
        {"full_session_export_sha256": _sha256(full_path)},
    )

    report = audit_full_group(root)
    errors = {(item.code, item.scope) for item in report.errors}

    assert report.passed is False
    assert ("reflection_export_continuity_invalid", task_id) in errors
    assert ("reflection_prefix_flags_invalid", task_id) not in errors
    assert ("reflection_runtime_delivered_hash_invalid", task_id) not in errors


def test_delivered_reflection_validator_session_must_match_result(
    tmp_path: Path,
) -> None:
    root = _make_group(tmp_path)
    task_id = "E1-LS1-T1"
    audit, _record, _lifecycle = _reflection_fixture_paths(root, task_id)
    solve_path = audit / "trajectory.solve.json"
    full_path = audit / "trajectory.full.json"
    for path in (solve_path, full_path):
        payload = json.loads(path.read_text(encoding="utf-8"))
        payload["session_id"] = "different-valid-session"
        _write_json(path, payload)
    _sync_reflection_fields(
        root,
        task_id,
        {
            "solve_trajectory_sha256": _sha256(solve_path),
            "full_session_trajectory_sha256": _sha256(full_path),
        },
    )

    report = audit_full_group(root)
    errors = {(item.code, item.scope) for item in report.errors}

    assert report.passed is False
    assert ("reflection_trajectory_session_mismatch", task_id) in errors
    assert ("reflection_trajectory_continuity_invalid", task_id) not in errors
    assert ("reflection_runtime_delivered_hash_invalid", task_id) not in errors


def test_missing_environment_fails_group_completeness(tmp_path: Path) -> None:
    root = _make_group(tmp_path)
    (
        root / "jobs" / "job-e6" / "artifacts" / "output" / "dataset_episode.json"
    ).unlink()

    report = audit_full_group(root)

    assert report.passed is False
    assert "E6" not in report.observed_environments
    assert any(item.code == "environment_set_incomplete" for item in report.errors)


def test_delivered_artifact_digest_mismatch_fails_closed(tmp_path: Path) -> None:
    root = _make_group(tmp_path)
    (root / "jobs" / "job-e3" / "artifacts" / "output" / "preflight.log").write_text(
        "tampered after sanitization\n", encoding="utf-8"
    )

    report = audit_full_group(root)

    assert report.passed is False
    assert any(
        item.scope == "E3" and item.code == "sanitization_manifest_invalid"
        for item in report.errors
    )


def test_group_aggregate_is_recomputed_from_raw_environment_metrics(
    tmp_path: Path,
) -> None:
    root = _make_group(tmp_path)
    path = root / "jobs" / "job-post-process" / "artifacts" / "output" / "metrics.json"
    metrics = json.loads(path.read_text(encoding="utf-8"))
    metrics["evaluation_sr"] = 0.5
    _write_json(path, metrics)

    report = audit_full_group(root)

    assert report.passed is False
    assert report.group_post_process_verified is False
    assert any(
        item.code == "group_post_process_aggregate_mismatch" for item in report.errors
    )


def test_standalone_jobs_compose_and_pass_the_full_audit(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    output = tmp_path / "local-composition"

    compose_standalone_full(
        exports.values(),
        output_root=output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
        expected_split=EXPECTED_SPLIT,
    )

    group = json.loads((output / "group.json").read_text(encoding="utf-8"))
    manifest = json.loads(
        (output / "composition_manifest.json").read_text(encoding="utf-8")
    )
    aggregate = json.loads(
        (
            output
            / "jobs"
            / "local-post-process"
            / "artifacts"
            / "output"
            / "metrics.json"
        ).read_text(encoding="utf-8")
    )
    assert group["composition_mode"] == COMPOSITION_MODE
    assert group["ap_group_id"] is None
    assert manifest["composition_mode"] == COMPOSITION_MODE
    assert manifest["ap_group_id"] is None
    assert aggregate["t4_transfer"] == pytest.approx(0.35)
    assert aggregate["fail_to_success_count"] == 21
    assert aggregate["cross_task_success_to_fail_count"] == 15
    assert aggregate["selected_job_ids"] == {
        environment_id: f"standalone-{environment_id.lower()}"
        for environment_id in EXPECTED_ENVIRONMENTS
    }
    assert not list(output.rglob("artifacts.json"))
    assert SIGNED_URL_MARKER not in json.dumps(manifest, sort_keys=True)
    assert (
        manifest["source_jobs"]["E1"]["source_projected_tree"][
            "excluded_artifacts_json"
        ]
        == 1
    )
    assert (
        manifest["source_jobs"]["E1"]["copied_projected_tree"][
            "excluded_artifacts_json"
        ]
        == 0
    )
    assert manifest["source_jobs"]["E1"]["source_safety_scan"]["clean"] is True
    assert manifest["source_jobs"]["E1"]["copied_safety_scan"]["clean"] is True
    assert output.stat().st_mode & 0o7777 == 0o700
    assert (output / "group.json").stat().st_mode & 0o7777 == 0o600
    assert (output / "jobs" / "standalone-e1").stat().st_mode & 0o7777 == 0o700
    assert (
        output / "jobs" / "standalone-e1" / "job.json"
    ).stat().st_mode & 0o7777 == 0o600

    report = audit_full_group(
        output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
    )

    assert report.passed is True
    assert report.composition_mode == COMPOSITION_MODE
    assert report.aggregation_origin == "local_postprocess"
    assert report.group_post_process_verified is True


def test_standalone_composition_rejects_grouped_source_before_writing(
    tmp_path: Path,
) -> None:
    exports = _make_standalone_exports(tmp_path)
    job_path = exports["E1"] / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["group_id"] = "real-ap-group"
    _write_json(job_path, job)
    output = tmp_path / "must-not-exist"

    with pytest.raises(CompositionError):
        compose_standalone_full(
            exports.values(),
            output_root=output,
            expected_benchmark_revision=BENCHMARK_REVISION,
            expected_agenthub_revision=AGENTHUB_REVISION,
            expected_split=EXPECTED_SPLIT,
        )

    assert not output.exists()


def test_local_composition_job_metadata_tamper_fails_audit(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    output = tmp_path / "local-composition"
    compose_standalone_full(
        exports.values(),
        output_root=output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
        expected_split=EXPECTED_SPLIT,
    )
    job_path = output / "jobs" / "standalone-e4" / "job.json"
    job = json.loads(job_path.read_text(encoding="utf-8"))
    job["k8s_namespace"] = "unexpected-namespace"
    _write_json(job_path, job)

    report = audit_full_group(output)

    assert report.passed is False
    assert any(
        item.scope == "E4" and item.code == "composition_job_metadata_invalid"
        for item in report.errors
    )
    assert any(
        item.scope == "E4" and item.code == "composition_source_hash_mismatch"
        for item in report.errors
    )


def test_standalone_composition_rejects_full_tree_safety_finding(
    tmp_path: Path,
) -> None:
    exports = _make_standalone_exports(tmp_path)
    (exports["E2"] / "unsafe-evidence.txt").write_text(
        "sevb-no-auth-must-not-survive\n",
        encoding="utf-8",
    )
    output = tmp_path / "must-not-exist"

    with pytest.raises(CompositionError):
        compose_standalone_full(
            exports.values(),
            output_root=output,
            expected_benchmark_revision=BENCHMARK_REVISION,
            expected_agenthub_revision=AGENTHUB_REVISION,
            expected_split=EXPECTED_SPLIT,
        )

    assert not output.exists()


def test_standalone_composition_rejects_escaping_symlink(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    outside = tmp_path / "outside.txt"
    outside.write_text("outside\n", encoding="utf-8")
    (exports["E3"] / "escape-link").symlink_to(outside)
    output = tmp_path / "must-not-exist"

    with pytest.raises(CompositionError):
        compose_standalone_full(
            exports.values(),
            output_root=output,
            expected_benchmark_revision=BENCHMARK_REVISION,
            expected_agenthub_revision=AGENTHUB_REVISION,
            expected_split=EXPECTED_SPLIT,
        )

    assert not output.exists()


def test_local_composition_noncore_file_tamper_fails_audit(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    output = tmp_path / "local-composition"
    compose_standalone_full(
        exports.values(),
        output_root=output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
        expected_split=EXPECTED_SPLIT,
    )
    added = output / "jobs" / "standalone-e3" / "unexpected-evidence.txt"
    added.write_text("added after composition\n", encoding="utf-8")
    added.chmod(0o600)

    report = audit_full_group(output)

    assert report.passed is False
    assert any(
        item.scope == "E3" and item.code == "composition_copied_tree_mismatch"
        for item in report.errors
    )


def test_local_composition_permission_tamper_fails_audit(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    output = tmp_path / "local-composition"
    compose_standalone_full(
        exports.values(),
        output_root=output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
        expected_split=EXPECTED_SPLIT,
    )
    (output / "group.json").chmod(0o644)

    report = audit_full_group(output)

    assert report.passed is False
    assert any(
        item.scope == "group" and item.code == "composition_private_permissions_invalid"
        for item in report.errors
    )


def test_local_composition_aggregate_tamper_fails_audit(tmp_path: Path) -> None:
    exports = _make_standalone_exports(tmp_path)
    output = tmp_path / "local-composition"
    compose_standalone_full(
        exports.values(),
        output_root=output,
        expected_benchmark_revision=BENCHMARK_REVISION,
        expected_agenthub_revision=AGENTHUB_REVISION,
        expected_split=EXPECTED_SPLIT,
    )
    metrics_path = (
        output / "jobs" / "local-post-process" / "artifacts" / "output" / "metrics.json"
    )
    aggregate = json.loads(metrics_path.read_text(encoding="utf-8"))
    aggregate["evaluation_sr"] = 0.5
    _write_json(metrics_path, aggregate)
    metrics_path.chmod(0o600)

    report = audit_full_group(output)

    assert report.passed is False
    assert any(
        item.scope == "group" and item.code == "composition_local_metrics_hash_mismatch"
        for item in report.errors
    )
    assert any(
        item.scope == "group" and item.code == "composition_local_aggregate_mismatch"
        for item in report.errors
    )
