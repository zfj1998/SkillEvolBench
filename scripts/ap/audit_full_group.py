#!/usr/bin/env python3
"""Fail-closed, read-only audit for a full SkillEvolBench AP group export.

The expected input is either the directory produced by ``ap group export`` or
the explicitly labelled local root produced by ``compose_standalone_full.py``.
An AP group must include its post-process job below ``jobs/<job-id>``; a local
composition must include its strict composition manifest and copied standalone
job metadata.  Its semantic audit only opens a fixed allowlist of
benchmark-owned JSON/YAML/text artifacts.  A local composition additionally
receives a secret-safe full-tree scan that reports aggregate counts only.  The
auditor never opens AP ``artifacts.json``/download-link metadata, and it never
prints model endpoints, submitted parameters, artifact URLs, or file contents.

Exit status is ``0`` only when all six canonical environment episodes and the
group post-process result pass every integrity check.  Integrity failures use
exit status ``2``; malformed invocation/input paths use ``1``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

import yaml

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ap.mask_secrets import (  # noqa: E402
    _read_manifest as read_sanitization_manifest,
)
from scripts.ap.compose_standalone_full import (  # noqa: E402
    AGGREGATION_METHOD,
    COMPOSITION_MODE,
    COMPOSITION_SCHEMA_VERSION,
    EXPECTED_NAMESPACE,
    LOCAL_METRICS_RELATIVE_PATH,
    LOCAL_POSTPROCESS_JOB_ID,
    build_aggregate_metrics,
    build_composition_id,
    canonical_metric_errors,
    private_permissions_valid,
    summarize_projected_tree,
)
from scripts.ap.scan_export_safety import (  # noqa: E402
    ALL_CATEGORIES as SAFETY_SCAN_CATEGORIES,
)
from scripts.ap.scan_export_safety import (  # noqa: E402
    ALL_SURFACES as SAFETY_SCAN_SURFACES,
)
from scripts.ap.scan_export_safety import (  # noqa: E402
    SCHEMA_VERSION as SAFETY_SCAN_SCHEMA_VERSION,
)
from scripts.ap.scan_export_safety import ScanError, scan_tree  # noqa: E402


EXPECTED_ENVIRONMENTS = tuple(f"E{i}" for i in range(1, 7))
FAMILIES_PER_ENVIRONMENT = 5
TASKS_PER_FAMILY = 6
PRIMARY_PER_ENVIRONMENT = FAMILIES_PER_ENVIRONMENT * TASKS_PER_FAMILY
REFLECTIONS_PER_ENVIRONMENT = FAMILIES_PER_ENVIRONMENT * 3
EXPECTED_DATASET = "skillevolbench/skillevolbench"
EXPECTED_BASELINE = "selfgen_in_session_always"
EXPECTED_SPLIT = "v1@7"
EXPECTED_ORDER_SEED = "A"
TASK_ROLES = {
    1: ("canonical", "learning"),
    2: ("enriched", "learning"),
    3: ("variant", "learning"),
    4: ("context-shift", "evaluation"),
    5: ("adversarial", "evaluation"),
    6: ("composition", "evaluation"),
}
TERMINAL_REFLECTION_STATUSES = frozenset({"completed", "noop", "rejected"})
ALL_REFLECTION_STATUSES = ("completed", "noop", "rejected", "skipped")
TRANSITION_KEYS = (
    "fail_to_success_count",
    "fail_to_fail_count",
    "success_to_success_count",
    "success_to_fail_count",
)
REFLECTION_EVENT_TYPES = frozenset(
    {"reflection_completed", "reflection_noop", "reflection_rejected"}
)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+-]{0,199}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SHA256_ID = re.compile(r"^sha256:[0-9a-f]{64}$")


@dataclass(frozen=True)
class Finding:
    """One secret-safe audit diagnostic."""

    code: str
    scope: str


@dataclass
class EnvironmentSummary:
    """Safe summary fields retained for one environment."""

    environment_id: str
    run_id: str = "unknown"
    status: str = "unknown"
    scoreable: bool = False
    metric_passed: bool | None = None
    task_score: float | None = None
    evaluation_sr: float | None = None
    primary_trials: int = 0
    replay_trials: int = 0
    reflection_terminal: int = 0
    same_session_verified: int = 0
    reflection_transfer_pairs: int = 0
    reflection_transitions: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in TRANSITION_KEYS}
    )
    reflection_by_status: dict[str, dict[str, int]] = field(default_factory=dict)
    revision_applied: int = 0
    revision_cross_task_pairs: int = 0
    revision_transitions: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in TRANSITION_KEYS}
    )
    manifest_changed_files: int = 0
    benchmark_revision: str = "unknown"
    source_archive_sha256: str = "unknown"
    benchmark_hash: str = "unknown"
    harbor_revision: str = "unknown"
    agent_runtime_image: str = "unknown"
    model_id_sha256: str = "unknown"
    errors: list[Finding] = field(default_factory=list)

    @property
    def passed(self) -> bool:
        return not self.errors


@dataclass
class AuditReport:
    """Complete six-environment audit result."""

    schema_version: int = 1
    passed: bool = False
    group_id: str = "unknown"
    expected_environments: list[str] = field(
        default_factory=lambda: list(EXPECTED_ENVIRONMENTS)
    )
    observed_environments: list[str] = field(default_factory=list)
    selected_job_count: int = 0
    group_post_process_verified: bool = False
    composition_mode: str = "ap_group"
    aggregation_origin: str = "ap_group_post_process"
    benchmark_revision: str = "unknown"
    agenthub_revision: str = "unknown"
    dataset: str = "unknown"
    split: str = "unknown"
    total_primary_trials: int = 0
    total_replay_trials: int = 0
    total_reflection_terminal: int = 0
    total_same_session_verified: int = 0
    reflection_transfer_pairs: int = 0
    reflection_transitions: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in TRANSITION_KEYS}
    )
    reflection_by_status: dict[str, dict[str, int]] = field(default_factory=dict)
    revision_applied: int = 0
    revision_cross_task_pairs: int = 0
    revision_transitions: dict[str, int] = field(
        default_factory=lambda: {key: 0 for key in TRANSITION_KEYS}
    )
    transition_interpretation: str = (
        "observational_only; causal claims require a matched control"
    )
    environments: dict[str, EnvironmentSummary] = field(default_factory=dict)
    errors: list[Finding] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["environments"] = {
            key: asdict(value) for key, value in sorted(self.environments.items())
        }
        return payload


class AuditContext:
    """Collect findings without ever interpolating artifact values."""

    def __init__(self) -> None:
        self.errors: list[Finding] = []

    def error(self, code: str, scope: str) -> None:
        self.errors.append(Finding(code=code, scope=scope))


def _safe_identifier(value: Any, *, fallback: str = "unknown") -> str:
    if isinstance(value, str) and SAFE_ID.fullmatch(value):
        return value
    return fallback


def _is_git_or_sha256_hash(value: Any) -> bool:
    return isinstance(value, str) and bool(
        HEX40.fullmatch(value) or HEX64.fullmatch(value)
    )


def _load_json_object(
    path: Path,
    *,
    context: AuditContext,
    code: str,
    scope: str,
) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        context.error(f"{code}_missing", scope)
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        context.error(f"{code}_invalid", scope)
        return None
    if not isinstance(value, dict):
        context.error(f"{code}_not_object", scope)
        return None
    return value


def _load_jsonl_objects(
    path: Path,
    *,
    context: AuditContext,
    code: str,
    scope: str,
) -> list[dict[str, Any]] | None:
    if path.is_symlink() or not path.is_file():
        context.error(f"{code}_missing", scope)
        return None
    rows: list[dict[str, Any]] = []
    try:
        with path.open("r", encoding="utf-8") as stream:
            for line in stream:
                if not line.strip():
                    continue
                value = json.loads(line)
                if not isinstance(value, dict):
                    context.error(f"{code}_row_not_object", scope)
                    return None
                rows.append(value)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        context.error(f"{code}_invalid", scope)
        return None
    return rows


def _load_yaml_object(
    path: Path,
    *,
    context: AuditContext,
    code: str,
    scope: str,
) -> dict[str, Any] | None:
    if path.is_symlink() or not path.is_file():
        context.error(f"{code}_missing", scope)
        return None
    try:
        value = yaml.safe_load(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, yaml.YAMLError):
        context.error(f"{code}_invalid", scope)
        return None
    if not isinstance(value, dict):
        context.error(f"{code}_not_object", scope)
        return None
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _is_regular_beneath(root: Path, path: Path) -> bool:
    """Return true only when every path component stays non-symlinked."""

    try:
        relative = path.relative_to(root)
    except ValueError:
        return False
    cursor = root
    if cursor.is_symlink() or not cursor.is_dir():
        return False
    for part in relative.parts:
        cursor = cursor / part
        if cursor.is_symlink():
            return False
    return cursor.is_file()


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _same_number(left: Any, right: Any) -> bool:
    return (
        _is_number(left)
        and _is_number(right)
        and math.isfinite(float(left))
        and math.isfinite(float(right))
        and math.isclose(float(left), float(right), rel_tol=0.0, abs_tol=1e-9)
    )


def _unit_interval_number(value: Any) -> bool:
    return (
        _is_number(value) and math.isfinite(float(value)) and 0.0 <= float(value) <= 1.0
    )


def _nonnegative_int(value: Any) -> bool:
    return type(value) is int and value >= 0


def _count_or_zero(value: Any) -> int:
    return int(value) if _nonnegative_int(value) else 0


def _transition_counts(
    section: dict[str, Any],
) -> dict[str, int] | None:
    counts = {key: section.get(key) for key in TRANSITION_KEYS}
    if not all(_nonnegative_int(value) for value in counts.values()):
        return None
    return {key: int(value) for key, value in counts.items()}


def _validate_reflection_transfer(
    section: Any,
    *,
    environment_id: str,
    run_root: Path,
    context: AuditContext,
) -> tuple[int, dict[str, int], dict[str, dict[str, int]]]:
    empty = {key: 0 for key in TRANSITION_KEYS}
    if not isinstance(section, dict):
        context.error("reflection_transfer_missing", environment_id)
        return 0, empty, {}
    n_pairs = section.get("n_pairs")
    counts = _transition_counts(section)
    pairs = section.get("pairs")
    by_status = section.get("by_reflection_status")
    if not (
        n_pairs == REFLECTIONS_PER_ENVIRONMENT
        and counts is not None
        and sum(counts.values()) == n_pairs
        and isinstance(pairs, list)
        and len(pairs) == n_pairs
        and isinstance(by_status, dict)
        and set(by_status) == set(ALL_REFLECTION_STATUSES)
    ):
        context.error("reflection_transfer_counts_invalid", environment_id)
        return _count_or_zero(n_pairs), counts or empty, {}

    expected_sources = {
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, FAMILIES_PER_ENVIRONMENT + 1)
        for tier in range(1, 4)
    }
    seen_sources: set[str] = set()
    observed_by_status: dict[str, dict[str, int]] = {
        status: {"n_pairs": 0, **{key: 0 for key in TRANSITION_KEYS}}
        for status in ALL_REFLECTION_STATUSES
    }
    valid = True
    for pair in pairs:
        if not isinstance(pair, dict):
            valid = False
            continue
        source_id = pair.get("source_task_id")
        next_id = pair.get("next_task_id")
        status = pair.get("reflection_status")
        transition = pair.get("transition")
        source_parts = _task_parts(source_id) if isinstance(source_id, str) else None
        next_parts = _task_parts(next_id) if isinstance(next_id, str) else None
        expected_transition = None
        if isinstance(pair.get("source_passed"), bool) and isinstance(
            pair.get("next_passed"), bool
        ):
            expected_transition = (
                "success_to_success"
                if pair["source_passed"] and pair["next_passed"]
                else "success_to_fail"
                if pair["source_passed"]
                else "fail_to_success"
                if pair["next_passed"]
                else "fail_to_fail"
            )
        transition_key = f"{transition}_count"
        if not (
            source_id in expected_sources
            and source_id not in seen_sources
            and source_parts is not None
            and next_parts is not None
            and source_parts[:2] == next_parts[:2]
            and next_parts[2] == source_parts[2] + 1
            and pair.get("family_id") == source_parts[1]
            and status in ALL_REFLECTION_STATUSES
            and transition_key in TRANSITION_KEYS
            and transition == expected_transition
        ):
            valid = False
            continue
        source_record = _load_json_object(
            run_root / "stores" / "replay" / "records" / f"{source_id}.json",
            context=context,
            code="reflection_transfer_source_record",
            scope=source_id,
        )
        next_record = _load_json_object(
            run_root / "stores" / "replay" / "records" / f"{next_id}.json",
            context=context,
            code="reflection_transfer_next_record",
            scope=source_id,
        )
        source_outcome = (
            source_record.get("outcome") if isinstance(source_record, dict) else None
        )
        next_outcome = (
            next_record.get("outcome") if isinstance(next_record, dict) else None
        )
        source_reflection = (
            source_record.get("reflection") if isinstance(source_record, dict) else None
        )
        if not (
            isinstance(source_outcome, dict)
            and isinstance(next_outcome, dict)
            and isinstance(source_reflection, dict)
            and source_reflection.get("status") == status
            and bool(source_outcome.get("verifier_passed")) == pair["source_passed"]
            and bool(next_outcome.get("verifier_passed")) == pair["next_passed"]
        ):
            valid = False
            continue
        seen_sources.add(source_id)
        observed_by_status[str(status)]["n_pairs"] += 1
        observed_by_status[str(status)][transition_key] += 1
    if seen_sources != expected_sources or not valid:
        context.error("reflection_transfer_pairs_invalid", environment_id)

    safe_by_status: dict[str, dict[str, int]] = {}
    for status in ALL_REFLECTION_STATUSES:
        status_section = by_status.get(status)
        status_counts = (
            _transition_counts(status_section)
            if isinstance(status_section, dict)
            else None
        )
        if not (
            isinstance(status_section, dict)
            and _nonnegative_int(status_section.get("n_pairs"))
            and status_counts is not None
        ):
            valid = False
            continue
        safe = {"n_pairs": int(status_section["n_pairs"]), **status_counts}
        safe_by_status[status] = safe
        if safe != observed_by_status[status]:
            valid = False
    if not valid:
        context.error("reflection_transfer_by_status_invalid", environment_id)
    return _count_or_zero(n_pairs), counts, safe_by_status


def _validate_revision_safety(
    section: Any,
    *,
    environment_id: str,
    context: AuditContext,
) -> tuple[int, int, dict[str, int]]:
    empty = {key: 0 for key in TRANSITION_KEYS}
    if not isinstance(section, dict):
        context.error("revision_safety_missing", environment_id)
        return 0, 0, empty
    n_applied = section.get("n_applied")
    n_pairs = section.get("n_cross_task_revision_pairs")
    counts = _transition_counts(section)
    if not (
        _nonnegative_int(n_applied)
        and _nonnegative_int(n_pairs)
        and n_pairs <= n_applied
        and n_pairs <= REFLECTIONS_PER_ENVIRONMENT
        and counts is not None
        and sum(counts.values()) == n_pairs
    ):
        context.error("revision_safety_counts_invalid", environment_id)
        return _count_or_zero(n_applied), _count_or_zero(n_pairs), counts or empty
    return _count_or_zero(n_applied), _count_or_zero(n_pairs), counts


def _expected_task_order(environment_id: str) -> list[str]:
    learning = [
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, FAMILIES_PER_ENVIRONMENT + 1)
        for tier in range(1, 4)
    ]
    evaluation = [
        f"{environment_id}-LS{family}-T{tier}"
        for family in range(1, FAMILIES_PER_ENVIRONMENT + 1)
        for tier in range(4, 7)
    ]
    return learning + evaluation


def _task_parts(task_id: str) -> tuple[str, str, int] | None:
    match = re.fullmatch(r"(E[1-6])-(LS[1-5])-T([1-6])", task_id)
    if match is None:
        return None
    return match.group(1), f"{match.group(1)}-{match.group(2)}", int(match.group(3))


def _discover_run(
    output_root: Path,
    *,
    context: AuditContext,
    scope: str,
) -> Path | None:
    runs_root = output_root / "runs"
    if runs_root.is_symlink() or not runs_root.is_dir():
        context.error("runs_root_missing", scope)
        return None
    candidates = sorted(
        child
        for child in runs_root.iterdir()
        if child.is_dir() and (child / "reports" / "full_report.json").is_file()
    )
    if len(candidates) != 1:
        context.error("run_count_not_one", scope)
        return None
    return candidates[0]


def _load_manifest(
    output_root: Path,
    *,
    context: AuditContext,
    scope: str,
) -> dict[str, dict[str, str | int]]:
    try:
        manifest = read_sanitization_manifest(output_root)
    except RuntimeError:
        context.error("sanitization_manifest_invalid", scope)
        return {}
    if manifest is None:
        context.error("sanitization_manifest_missing", scope)
        return {}
    for entry in manifest.values():
        if (
            entry["runtime_sha256"] == entry["delivered_sha256"]
            and entry["runtime_size"] == entry["delivered_size"]
        ):
            context.error("sanitization_manifest_unchanged_entry", scope)
            break
    return manifest


def _runtime_hash_status(
    path: Path,
    expected_runtime_hash: Any,
    *,
    output_root: Path,
    manifest: dict[str, dict[str, str | int]],
) -> bool:
    if (
        path.is_symlink()
        or not path.is_file()
        or not isinstance(expected_runtime_hash, str)
        or HEX64.fullmatch(expected_runtime_hash) is None
    ):
        return False
    delivered_hash = _sha256_file(path)
    if delivered_hash == expected_runtime_hash:
        return True
    try:
        relative = (
            path.resolve(strict=True)
            .relative_to(output_root.resolve(strict=True))
            .as_posix()
        )
    except (FileNotFoundError, ValueError):
        return False
    entry = manifest.get(relative)
    return bool(
        entry
        and entry.get("runtime_sha256") == expected_runtime_hash
        and entry.get("delivered_sha256") == delivered_hash
        and entry.get("delivered_size") == path.stat().st_size
    )


def _stream_session_ids(
    path: Path,
    *,
    context: AuditContext,
    scope: str,
) -> set[str] | None:
    rows = _load_jsonl_objects(
        path,
        context=context,
        code="reflection_stream",
        scope=scope,
    )
    if rows is None:
        return None
    ids: set[str] = set()
    for row in rows:
        value = row.get("sessionID") or row.get("session_id")
        if not isinstance(value, str) or not value:
            context.error("reflection_stream_session_missing", scope)
            return None
        ids.add(value)
    return ids


def _validate_strict_prefix(
    solve_path: Path,
    full_path: Path,
    *,
    list_key: str,
    context: AuditContext,
    code: str,
    scope: str,
) -> None:
    solve = _load_json_object(
        solve_path,
        context=context,
        code=f"{code}_solve",
        scope=scope,
    )
    full = _load_json_object(
        full_path,
        context=context,
        code=f"{code}_full",
        scope=scope,
    )
    if solve is None or full is None:
        return
    solve_rows = solve.get(list_key)
    full_rows = full.get(list_key)
    if (
        not isinstance(solve_rows, list)
        or not isinstance(full_rows, list)
        or len(full_rows) <= len(solve_rows)
        or full_rows[: len(solve_rows)] != solve_rows
    ):
        context.error(f"{code}_not_strict_prefix", scope)


def _validate_reflection(
    *,
    task_id: str,
    trial_root: Path,
    record: dict[str, Any],
    event: dict[str, Any] | None,
    verifier_reward: dict[str, Any],
    output_root: Path,
    manifest: dict[str, dict[str, str | int]],
    context: AuditContext,
) -> None:
    scope = task_id
    audit = trial_root / "self-reflection-audit"
    result = _load_json_object(
        audit / "self_reflection_result.json",
        context=context,
        code="reflection_result",
        scope=scope,
    )
    reflection = record.get("reflection")
    if result is None or not isinstance(reflection, dict):
        context.error("reflection_record_missing", scope)
        return

    status = result.get("status")
    expected_event = f"reflection_{status}"
    if status not in TERMINAL_REFLECTION_STATUSES:
        context.error("reflection_status_not_terminal", scope)
    if event is None or event.get("event_type") != expected_event:
        context.error("reflection_event_mismatch", scope)

    compared = (
        "status",
        "task_id",
        "mode",
        "reason",
        "session_id",
        "solve_session_id",
        "reflection_session_id",
        "same_session_verified",
        "trajectory_prefix_verified",
        "export_prefix_verified",
        "task_workspace_hash_before",
        "task_workspace_hash_after",
        "prompt_sha256",
        "solve_trajectory_sha256",
        "full_session_trajectory_sha256",
        "solve_session_export_sha256",
        "full_session_export_sha256",
    )
    for key in compared:
        if reflection.get(key) != result.get(key) or (
            event is not None and event.get(key) != result.get(key)
        ):
            context.error("reflection_record_event_result_mismatch", scope)
            break

    session = result.get("session_id")
    if not (
        isinstance(session, str)
        and session
        and result.get("same_session_verified") is True
        and session
        == result.get("solve_session_id")
        == result.get("reflection_session_id")
    ):
        context.error("reflection_same_session_invalid", scope)
    if not (
        result.get("trajectory_prefix_verified") is True
        and result.get("export_prefix_verified") is True
    ):
        context.error("reflection_prefix_flags_invalid", scope)
    before = result.get("task_workspace_hash_before")
    after = result.get("task_workspace_hash_after")
    if not (isinstance(before, str) and HEX64.fullmatch(before) and before == after):
        context.error("reflection_workspace_hash_invalid", scope)

    solve_ids = _stream_session_ids(
        audit / "opencode.solve.jsonl", context=context, scope=scope
    )
    reflection_ids = _stream_session_ids(
        audit / "opencode.reflection.jsonl", context=context, scope=scope
    )
    if solve_ids != {session} or reflection_ids != {session}:
        context.error("reflection_stream_session_mismatch", scope)

    expected_hashes = {
        "prompt_sha256": audit / "self_reflection_prompt.md",
        "solve_trajectory_sha256": audit / "trajectory.solve.json",
        "full_session_trajectory_sha256": audit / "trajectory.full.json",
        "solve_session_export_sha256": audit / "opencode.session.solve.json",
        "full_session_export_sha256": audit / "opencode.session.full.json",
    }
    for field_name, path in expected_hashes.items():
        if not _runtime_hash_status(
            path,
            result.get(field_name),
            output_root=output_root,
            manifest=manifest,
        ):
            context.error("reflection_runtime_delivered_hash_invalid", scope)
            break

    _validate_strict_prefix(
        audit / "trajectory.solve.json",
        audit / "trajectory.full.json",
        list_key="steps",
        context=context,
        code="reflection_trajectory",
        scope=scope,
    )
    _validate_strict_prefix(
        audit / "opencode.session.solve.json",
        audit / "opencode.session.full.json",
        list_key="messages",
        context=context,
        code="reflection_export",
        scope=scope,
    )

    required = [
        audit / "self_reflection_feedback.json",
        audit / "official-verifier" / "reward.json",
    ]
    if status == "completed":
        required.append(audit / "self_reflection_patch.json")
    if any(path.is_symlink() or not path.is_file() for path in required):
        context.error("reflection_required_artifact_missing", scope)

    official = _load_json_object(
        audit / "official-verifier" / "reward.json",
        context=context,
        code="reflection_official_verifier",
        scope=scope,
    )
    if official is not None:
        for key in (
            "normalized_score",
            "total_score",
            "max_score",
            "outcome_passed",
            "process_passed",
        ):
            if official.get(key) != verifier_reward.get(key):
                context.error("reflection_verifier_snapshot_mismatch", scope)
                break


def _validate_lifecycle(
    *,
    environment_id: str,
    rows: list[dict[str, Any]],
    context: AuditContext,
) -> dict[str, dict[str, Any]]:
    relevant_types = {
        "trial_started",
        "trial_ended_learning",
        "trial_ended_eval",
        "library_frozen",
        "library_unfrozen",
        "library_swap_on_env_transition",
        "env_transition",
        *REFLECTION_EVENT_TYPES,
    }
    relevant = [row for row in rows if row.get("event_type") in relevant_types]
    expected_order = _expected_task_order(environment_id)
    expected: list[tuple[str, str | None]] = []
    for task_id in expected_order[:REFLECTIONS_PER_ENVIRONMENT]:
        expected.extend(
            [
                ("trial_started", task_id),
                ("reflection_terminal", task_id),
                ("trial_ended_learning", task_id),
            ]
        )
    expected.append(("library_frozen", None))
    for task_id in expected_order[REFLECTIONS_PER_ENVIRONMENT:]:
        expected.extend([("trial_started", task_id), ("trial_ended_eval", task_id)])
    expected.extend(
        [
            ("library_unfrozen", None),
            ("library_swap_on_env_transition", None),
            ("env_transition", None),
        ]
    )

    normalized: list[tuple[str, str | None]] = []
    reflection_events: dict[str, dict[str, Any]] = {}
    for row in relevant:
        event_type = row.get("event_type")
        task_id = row.get("task_id") if isinstance(row.get("task_id"), str) else None
        if event_type in REFLECTION_EVENT_TYPES:
            normalized.append(("reflection_terminal", task_id))
            if task_id in reflection_events:
                context.error("reflection_event_duplicate", environment_id)
            elif task_id is not None:
                reflection_events[task_id] = row
        else:
            normalized.append((str(event_type), task_id))
    if normalized != expected:
        context.error("lifecycle_sequence_invalid", environment_id)

    start_rows = [row for row in relevant if row.get("event_type") == "trial_started"]
    if [row.get("task_id") for row in start_rows] != expected_order:
        context.error("trial_start_order_invalid", environment_id)
    for row, task_id in zip(start_rows, expected_order):
        parts = _task_parts(task_id)
        if parts is None:
            continue
        expected_role = TASK_ROLES[parts[2]][0]
        if row.get("role") != expected_role:
            context.error("trial_start_role_invalid", task_id)

    freeze = [row for row in relevant if row.get("event_type") == "library_frozen"]
    unfreeze = [row for row in relevant if row.get("event_type") == "library_unfrozen"]
    swaps = [
        row
        for row in relevant
        if row.get("event_type") == "library_swap_on_env_transition"
    ]
    transitions = [row for row in relevant if row.get("event_type") == "env_transition"]
    if not (len(freeze) == len(unfreeze) == len(swaps) == len(transitions) == 1):
        context.error("lifecycle_boundary_count_invalid", environment_id)
        return reflection_events
    frozen_hash = freeze[0].get("hash")
    if not (
        freeze[0].get("env_id") == environment_id
        and _is_git_or_sha256_hash(frozen_hash)
    ):
        context.error("library_freeze_invalid", environment_id)
    if not (
        unfreeze[0].get("env_id") == environment_id
        and unfreeze[0].get("n_patches_discarded") == 0
    ):
        context.error("library_unfreeze_invalid", environment_id)
    for row in (swaps[0], transitions[0]):
        if row.get("from_env") != environment_id or row.get("to_env") != "END":
            context.error("environment_end_transition_invalid", environment_id)
    if transitions[0].get("library_hash") != frozen_hash:
        context.error("frozen_library_hash_changed", environment_id)
    return reflection_events


def _validate_verifier_bundle(
    *,
    task_id: str,
    trial_root: Path,
    record: dict[str, Any],
    context: AuditContext,
) -> dict[str, Any] | None:
    verifier = trial_root / "verifier"
    required = (
        "reward.json",
        "reward.txt",
        "outcome_report.json",
        "process_report.json",
        "score_report.json",
    )
    if any(
        (verifier / name).is_symlink() or not (verifier / name).is_file()
        for name in required
    ):
        context.error("verifier_bundle_incomplete", task_id)
        return None
    reward = _load_json_object(
        verifier / "reward.json",
        context=context,
        code="verifier_reward",
        scope=task_id,
    )
    if reward is None:
        return None
    normalized = reward.get("normalized_score")
    if not (
        _is_number(normalized)
        and math.isfinite(float(normalized))
        and 0.0 <= float(normalized) <= 1.0
    ):
        context.error("verifier_score_invalid", task_id)
    try:
        reward_text = float(
            (verifier / "reward.txt").read_text(encoding="utf-8").strip()
        )
    except (OSError, UnicodeDecodeError, ValueError):
        context.error("verifier_reward_text_invalid", task_id)
    else:
        if not _same_number(normalized, reward_text):
            context.error("verifier_reward_text_mismatch", task_id)
    outcome = record.get("outcome")
    if not isinstance(outcome, dict):
        context.error("replay_outcome_missing", task_id)
        return reward
    if not (
        outcome.get("task_id") == task_id
        and _same_number(outcome.get("normalized_score"), normalized)
        and _same_number(outcome.get("reward"), normalized)
        and bool(outcome.get("verifier_passed")) == (float(normalized) >= 1.0)
    ):
        context.error("replay_verifier_disagreement", task_id)
    trajectory = trial_root / "agent" / "trajectory.solve.json"
    if trajectory.is_symlink() or not trajectory.is_file():
        context.error("solve_trajectory_missing", task_id)
    return reward


def _validate_task_records(
    *,
    environment_id: str,
    run_root: Path,
    output_root: Path,
    manifest: dict[str, dict[str, str | int]],
    reflection_events: dict[str, dict[str, Any]],
    frozen_hash: str | None,
    context: AuditContext,
) -> None:
    expected_order = _expected_task_order(environment_id)
    records_root = run_root / "stores" / "replay" / "records"
    if records_root.is_symlink() or not records_root.is_dir():
        context.error("replay_records_missing", environment_id)
        return
    actual_names = {
        path.name
        for path in records_root.glob("*.json")
        if path.is_file() and not path.is_symlink()
    }
    expected_names = {f"{task_id}.json" for task_id in expected_order}
    if actual_names != expected_names:
        context.error("replay_record_set_invalid", environment_id)

    harbor_root = run_root / "harbor-job" / run_root.name
    for index, task_id in enumerate(expected_order):
        record = _load_json_object(
            records_root / f"{task_id}.json",
            context=context,
            code="replay_record",
            scope=task_id,
        )
        if record is None:
            continue
        parts = _task_parts(task_id)
        assert parts is not None
        env_id, family_id, tier = parts
        expected_role, expected_phase = TASK_ROLES[tier]
        if not (
            record.get("task_id") == task_id
            and record.get("env_id") == env_id
            and record.get("family_id") == family_id
            and record.get("task_role") == expected_role
            and record.get("replay_mode") == "primary"
        ):
            context.error("replay_record_identity_invalid", task_id)

        task_spec = _load_yaml_object(
            run_root / "runtime" / task_id / "task-spec.yaml",
            context=context,
            code="runtime_task_spec",
            scope=task_id,
        )
        if task_spec is not None and not (
            task_spec.get("task_id") == task_id
            and task_spec.get("environment_id") == env_id
            and task_spec.get("family_id") == family_id
            and task_spec.get("role") == expected_role
            and task_spec.get("phase") == expected_phase
        ):
            context.error("runtime_task_role_invalid", task_id)

        outcome = record.get("outcome")
        trial_name = ""
        if isinstance(outcome, dict) and isinstance(outcome.get("trial_dir"), str):
            trial_name = PurePosixPath(outcome["trial_dir"]).name
        trial_root = harbor_root / trial_name if trial_name else Path()
        if (
            not trial_name.startswith(f"{task_id}__")
            or trial_root.is_symlink()
            or not trial_root.is_dir()
        ):
            matches = sorted(
                path
                for path in harbor_root.glob(f"{task_id}__*")
                if path.is_dir() and not path.is_symlink()
            )
            if len(matches) != 1:
                context.error("harbor_trial_count_invalid", task_id)
                continue
            trial_root = matches[0]

        reward = _validate_verifier_bundle(
            task_id=task_id,
            trial_root=trial_root,
            record=record,
            context=context,
        )
        if reward is None:
            continue
        if index < REFLECTIONS_PER_ENVIRONMENT:
            _validate_reflection(
                task_id=task_id,
                trial_root=trial_root,
                record=record,
                event=reflection_events.get(task_id),
                verifier_reward=reward,
                output_root=output_root,
                manifest=manifest,
                context=context,
            )
        else:
            reflection = record.get("reflection")
            if reflection not in ({}, None):
                context.error("evaluation_reflection_present", task_id)
            if (trial_root / "self-reflection-audit").exists():
                context.error("evaluation_reflection_audit_present", task_id)
            if frozen_hash is not None and not (
                record.get("library_hash_pre")
                == record.get("library_hash_post")
                == frozen_hash
            ):
                context.error("evaluation_library_hash_changed", task_id)


def _audit_environment(
    output_root: Path,
    *,
    expected_environment: str,
    expected_dataset: str,
    expected_split: str,
    expected_baseline: str,
    expected_order_seed: str,
) -> EnvironmentSummary:
    context = AuditContext()
    summary = EnvironmentSummary(environment_id=expected_environment)
    scope = expected_environment

    dataset = _load_json_object(
        output_root / "dataset_episode.json",
        context=context,
        code="dataset_episode",
        scope=scope,
    )
    manifest_payload = _load_json_object(
        output_root / "ap_run_manifest.json",
        context=context,
        code="ap_run_manifest",
        scope=scope,
    )
    metrics = _load_json_object(
        output_root / "metrics.json",
        context=context,
        code="metrics",
        scope=scope,
    )
    harbor = _load_json_object(
        output_root / "harbor_runtime.json",
        context=context,
        code="harbor_runtime",
        scope=scope,
    )
    agent_image = _load_json_object(
        output_root / "agent_runtime_image.json",
        context=context,
        code="agent_runtime_image",
        scope=scope,
    )
    host_probe = _load_json_object(
        output_root / "model_probe_host.json",
        context=context,
        code="model_probe_host",
        scope=scope,
    )
    dind_probe = _load_json_object(
        output_root / "model_probe_dind.json",
        context=context,
        code="model_probe_dind",
        scope=scope,
    )
    for label in ("preflight.log", "episode.log"):
        path = output_root / label
        if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
            context.error("runtime_log_missing_or_empty", scope)

    manifest = _load_manifest(output_root, context=context, scope=scope)
    summary.manifest_changed_files = len(manifest)
    run_root = _discover_run(output_root, context=context, scope=scope)
    if run_root is None:
        summary.errors = context.errors
        return summary

    report = _load_json_object(
        run_root / "reports" / "full_report.json",
        context=context,
        code="full_report",
        scope=scope,
    )
    config = _load_json_object(
        run_root / "config.json",
        context=context,
        code="run_config",
        scope=scope,
    )
    lifecycle = _load_jsonl_objects(
        run_root / "stores" / "events" / "lifecycle.jsonl",
        context=context,
        code="lifecycle",
        scope=scope,
    )

    if dataset is not None:
        summary.benchmark_revision = _safe_identifier(dataset.get("benchmark_revision"))
        summary.source_archive_sha256 = _safe_identifier(
            dataset.get("source_archive_sha256")
        )
        if not (
            dataset.get("schema_version") == "1.0"
            and dataset.get("dataset") == expected_dataset
            and dataset.get("split") == expected_split
            and dataset.get("instance_id") == expected_environment
            and dataset.get("environment_id") == expected_environment
            and dataset.get("family_count") == FAMILIES_PER_ENVIRONMENT
            and dataset.get("primary_task_count") == PRIMARY_PER_ENVIRONMENT
            and dataset.get("roles") == [f"T{i}" for i in range(1, 7)]
            and dataset.get("scoreable_unit") == "complete_environment_episode"
            and isinstance(dataset.get("benchmark_revision"), str)
            and HEX40.fullmatch(dataset["benchmark_revision"])
            and isinstance(dataset.get("source_archive_sha256"), str)
            and HEX64.fullmatch(dataset["source_archive_sha256"])
        ):
            context.error("dataset_provenance_invalid", scope)

    if manifest_payload is not None:
        summary.run_id = _safe_identifier(manifest_payload.get("run_id"))
        model = manifest_payload.get("model")
        if isinstance(model, str) and model:
            summary.model_id_sha256 = hashlib.sha256(model.encode("utf-8")).hexdigest()
        if not (
            manifest_payload.get("schema_version") == "1.0"
            and manifest_payload.get("benchmark_revision")
            == (dataset or {}).get("benchmark_revision")
            and manifest_payload.get("canonical") is True
            and manifest_payload.get("execution_scope") == "environment"
            and manifest_payload.get("environment_id") == expected_environment
            and manifest_payload.get("family_smoke_id") is None
            and manifest_payload.get("smoke_max_tasks") is None
            and manifest_payload.get("baseline_name") == expected_baseline
            and manifest_payload.get("order_seed") == expected_order_seed
            and manifest_payload.get("within_env_replay") is False
            and manifest_payload.get("replay_eval") is False
            and isinstance(model, str)
            and bool(model)
        ):
            context.error("run_manifest_invalid", scope)
        for probe, code in ((host_probe, "host"), (dind_probe, "dind")):
            probe_data = (probe or {}).get("data")
            ids = (
                [entry.get("id") for entry in probe_data if isinstance(entry, dict)]
                if isinstance(probe_data, list)
                else []
            )
            if (probe or {}).get("object") != "list" or model not in ids:
                context.error(f"model_probe_{code}_model_missing", scope)

    if metrics is not None:
        summary.status = str(metrics.get("status", "unknown"))
        summary.scoreable = metrics.get("scoreable") is True
        if type(metrics.get("passed")) is bool:
            summary.metric_passed = metrics["passed"]
        else:
            context.error("metrics_passed_invalid", scope)
        if _unit_interval_number(metrics.get("task_score")):
            summary.task_score = float(metrics["task_score"])
        else:
            context.error("task_score_invalid", scope)
        if _unit_interval_number(metrics.get("evaluation_sr")):
            summary.evaluation_sr = float(metrics["evaluation_sr"])
        else:
            context.error("evaluation_sr_invalid", scope)
        summary.primary_trials = _count_or_zero(metrics.get("n_primary_trials"))
        summary.replay_trials = _count_or_zero(metrics.get("n_replay_trials"))
        summary.reflection_terminal = _count_or_zero(
            metrics.get("n_reflection_terminal")
        )
        summary.same_session_verified = _count_or_zero(
            metrics.get("n_same_session_verified")
        )
        expected_metrics = {
            "status": "completed",
            "scoreable": True,
            "canonical": True,
            "execution_scope": "environment",
            "environment_id": expected_environment,
            "family_smoke_id": None,
            "baseline_name": expected_baseline,
            "n_primary_trials": PRIMARY_PER_ENVIRONMENT,
            "expected_primary_trials": PRIMARY_PER_ENVIRONMENT,
            "n_replay_trials": 0,
            "expected_replay_trials": 0,
            "n_shadow_trials": 0,
            "expected_shadow_trials": 0,
            "n_verifier_backed_trials": PRIMARY_PER_ENVIRONMENT,
            "expected_verifier_backed_trials": PRIMARY_PER_ENVIRONMENT,
            "reflection_enabled": True,
            "n_reflection_expected": REFLECTIONS_PER_ENVIRONMENT,
            "n_reflection_terminal": REFLECTIONS_PER_ENVIRONMENT,
            "n_reflection_attempted": REFLECTIONS_PER_ENVIRONMENT,
            "n_same_session_verified": REFLECTIONS_PER_ENVIRONMENT,
        }
        if any(metrics.get(key) != value for key, value in expected_metrics.items()):
            context.error("canonical_metrics_invalid", scope)
        if not _same_number(metrics.get("task_score"), metrics.get("evaluation_sr")):
            context.error("task_score_mismatch", scope)
        if metrics.get("run_id") != run_root.name:
            context.error("metrics_run_id_mismatch", scope)

    if report is not None:
        if not (
            report.get("schema_version") == "1.0"
            and report.get("run_id") == run_root.name
            and report.get("environment_id") == expected_environment
            and report.get("baseline_name") == expected_baseline
            and report.get("order_seed") == expected_order_seed
            and report.get("n_tasks_attempted") == PRIMARY_PER_ENVIRONMENT
            and report.get("n_primary_trials") == PRIMARY_PER_ENVIRONMENT
            and report.get("n_replay_trials") == 0
            and report.get("n_shadow_trials") == 0
        ):
            context.error("full_report_counts_invalid", scope)
        reflection = report.get("reflection")
        if not isinstance(reflection, dict) or not (
            reflection.get("enabled") is True
            and reflection.get("n_terminal") == REFLECTIONS_PER_ENVIRONMENT
            and reflection.get("n_attempted") == REFLECTIONS_PER_ENVIRONMENT
            and reflection.get("n_same_session_verified") == REFLECTIONS_PER_ENVIRONMENT
            and reflection.get("n_skipped") == 0
            and sum(
                int(reflection.get(key, 0) or 0)
                for key in ("n_completed", "n_noop", "n_rejected")
            )
            == REFLECTIONS_PER_ENVIRONMENT
        ):
            context.error("full_report_reflection_invalid", scope)
        task_success = report.get("task_success")
        if not isinstance(task_success, dict) or task_success.get("n_per_role") != {
            role: FAMILIES_PER_ENVIRONMENT for role, _phase in TASK_ROLES.values()
        }:
            context.error("full_report_role_counts_invalid", scope)
        (
            summary.reflection_transfer_pairs,
            summary.reflection_transitions,
            summary.reflection_by_status,
        ) = _validate_reflection_transfer(
            report.get("reflection_transfer"),
            environment_id=expected_environment,
            run_root=run_root,
            context=context,
        )
        (
            summary.revision_applied,
            summary.revision_cross_task_pairs,
            summary.revision_transitions,
        ) = _validate_revision_safety(
            report.get("revision_safety"),
            environment_id=expected_environment,
            context=context,
        )

    if config is not None and not (
        config.get("run_id") == run_root.name
        and config.get("environment_id") == expected_environment
        and config.get("family_smoke_id") is None
        and config.get("max_tasks") is None
        and config.get("order_seed") == expected_order_seed
    ):
        context.error("run_config_scope_invalid", scope)

    benchmark_hash_path = run_root / "benchmark_hash.txt"
    try:
        benchmark_hash = benchmark_hash_path.read_text(encoding="ascii").strip()
    except (OSError, UnicodeDecodeError):
        benchmark_hash = ""
    if HEX64.fullmatch(benchmark_hash) is None:
        context.error("benchmark_hash_invalid", scope)
    else:
        summary.benchmark_hash = benchmark_hash

    if harbor is not None and not (
        isinstance(harbor.get("version"), str)
        and bool(harbor["version"])
        and isinstance(harbor.get("requested_git_revision"), str)
        and HEX40.fullmatch(harbor["requested_git_revision"])
        and harbor.get("installed_git_commit") == harbor["requested_git_revision"]
    ):
        context.error("harbor_provenance_invalid", scope)
    elif harbor is not None:
        summary.harbor_revision = str(harbor["installed_git_commit"])
    if agent_image is not None:
        image_id = agent_image.get("id")
        repo_digests = agent_image.get("repo_digests")
        pinned = isinstance(image_id, str) and bool(SHA256_ID.fullmatch(image_id))
        digest_pinned = isinstance(repo_digests, list) and any(
            isinstance(value, str) and "@sha256:" in value for value in repo_digests
        )
        if not pinned and not digest_pinned:
            context.error("agent_runtime_image_unpinned", scope)
        elif pinned:
            summary.agent_runtime_image = str(image_id)
        else:
            pinned_digest = next(
                value.rsplit("@", 1)[-1]
                for value in repo_digests
                if isinstance(value, str) and "@sha256:" in value
            )
            summary.agent_runtime_image = pinned_digest

    reflection_events: dict[str, dict[str, Any]] = {}
    frozen_hash: str | None = None
    if lifecycle is not None:
        reflection_events = _validate_lifecycle(
            environment_id=expected_environment,
            rows=lifecycle,
            context=context,
        )
        freeze_rows = [
            row for row in lifecycle if row.get("event_type") == "library_frozen"
        ]
        if len(freeze_rows) == 1 and isinstance(freeze_rows[0].get("hash"), str):
            frozen_hash = freeze_rows[0]["hash"]
    _validate_task_records(
        environment_id=expected_environment,
        run_root=run_root,
        output_root=output_root,
        manifest=manifest,
        reflection_events=reflection_events,
        frozen_hash=frozen_hash,
        context=context,
    )

    summary.errors = context.errors
    return summary


def _discover_environment_outputs(
    group_root: Path,
    *,
    context: AuditContext,
) -> dict[str, list[Path]]:
    jobs_root = group_root / "jobs"
    if jobs_root.is_symlink() or not jobs_root.is_dir():
        context.error("jobs_root_missing", "group")
        return {}
    outputs: dict[str, list[Path]] = {}
    for job_dir in sorted(jobs_root.iterdir()):
        if job_dir.is_symlink() or not job_dir.is_dir():
            continue
        output_root = job_dir / "artifacts" / "output"
        dataset_path = output_root / "dataset_episode.json"
        if not _is_regular_beneath(job_dir, dataset_path):
            continue
        dataset_context = AuditContext()
        dataset = _load_json_object(
            dataset_path,
            context=dataset_context,
            code="dataset_episode",
            scope="job-output",
        )
        if dataset is None:
            context.error("job_dataset_episode_invalid", "group")
            continue
        environment_id = dataset.get("environment_id")
        if environment_id not in EXPECTED_ENVIRONMENTS:
            context.error("job_environment_id_invalid", "group")
            continue
        outputs.setdefault(str(environment_id), []).append(output_root)
    return outputs


def _safety_scan_proof_valid(
    report: Any,
    *,
    require_no_transport_metadata: bool,
) -> bool:
    if not isinstance(report, dict):
        return False
    expected_report_keys = {
        "schema_version",
        "clean",
        "scan_complete",
        "finding_count",
        "category_counts",
        "surface_counts",
        "scan_counts",
        "policy",
    }
    expected_scan_count_keys = {
        "bytes_scanned",
        "directories",
        "entries",
        "regular_files",
        "symlinks",
        "skipped_artifacts_json",
        "exact_secret_values_loaded",
        "exact_secret_values_ignored",
    }
    expected_policy = {
        "artifacts_json_content": "skipped_by_default",
        "finding_count_unit": "category_per_object_surface",
        "matched_values_reported": False,
        "paths_reported": False,
        "symlinks_followed": False,
        "writes_performed": False,
    }
    category_counts = report.get("category_counts")
    surface_counts = report.get("surface_counts")
    scan_counts = report.get("scan_counts")
    return bool(
        set(report) == expected_report_keys
        and report.get("schema_version") == SAFETY_SCAN_SCHEMA_VERSION
        and report.get("clean") is True
        and report.get("scan_complete") is True
        and report.get("finding_count") == 0
        and isinstance(category_counts, dict)
        and set(category_counts) == set(SAFETY_SCAN_CATEGORIES)
        and all(value == 0 for value in category_counts.values())
        and isinstance(surface_counts, dict)
        and set(surface_counts) == set(SAFETY_SCAN_SURFACES)
        and all(value == 0 for value in surface_counts.values())
        and isinstance(scan_counts, dict)
        and set(scan_counts) == expected_scan_count_keys
        and all(type(value) is int and value >= 0 for value in scan_counts.values())
        and (
            not require_no_transport_metadata
            or scan_counts.get("skipped_artifacts_json") == 0
        )
        and report.get("policy") == expected_policy
    )


def _tree_proof_valid(value: Any) -> bool:
    expected_keys = {
        "algorithm",
        "sha256",
        "directories",
        "regular_files",
        "symlinks",
        "regular_file_bytes",
        "excluded_artifacts_json",
    }
    return bool(
        isinstance(value, dict)
        and set(value) == expected_keys
        and value.get("algorithm") == "sha256_path_type_content_v1"
        and isinstance(value.get("sha256"), str)
        and HEX64.fullmatch(value["sha256"]) is not None
        and type(value.get("directories")) is int
        and value["directories"] >= 1
        and all(
            type(value.get(key)) is int and value[key] >= 0
            for key in (
                "regular_files",
                "symlinks",
                "regular_file_bytes",
                "excluded_artifacts_json",
            )
        )
    )


def _validate_local_composition(
    group_root: Path,
    group: dict[str, Any],
    *,
    expected_benchmark_revision: str | None,
    expected_agenthub_revision: str | None,
    expected_dataset: str,
    expected_split: str,
    expected_baseline: str,
    expected_order_seed: str,
    context: AuditContext,
) -> None:
    """Verify the provenance boundary of a standalone-job local composition."""

    manifest = _load_json_object(
        group_root / "composition_manifest.json",
        context=context,
        code="composition_manifest",
        scope="group",
    )
    if manifest is None:
        return

    expected_group_keys = {
        "schema_version",
        "composition_mode",
        "aggregation_origin",
        "ap_group_id",
        "group_id",
        "template",
        "dataset",
        "split",
        "benchmark_revision",
        "template_commit",
        "k8s_namespace",
        "composition_manifest",
        "expected_environments",
        "source_job_ids",
        "group_post_process_job_id",
        "stats",
    }
    expected_manifest_keys = {
        "schema_version",
        "composition_mode",
        "composition_id",
        "ap_group_id",
        "template",
        "dataset",
        "split",
        "benchmark_revision",
        "agenthub_revision",
        "k8s_namespace",
        "baseline_name",
        "order_seed",
        "expected_environments",
        "source_job_count",
        "source_jobs",
        "transport_metadata_policy",
        "permission_policy",
        "composition_safety_scan",
        "local_postprocess",
    }
    expected_stats = {
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
    }
    expected_environment_list = list(EXPECTED_ENVIRONMENTS)
    composition_id = manifest.get("composition_id")
    benchmark_revision = manifest.get("benchmark_revision")
    agenthub_revision = manifest.get("agenthub_revision")
    source_jobs = manifest.get("source_jobs")
    source_job_ids = group.get("source_job_ids")
    local_postprocess = manifest.get("local_postprocess")

    manifest_structure_valid = (
        set(manifest) == expected_manifest_keys
        and manifest.get("schema_version") == COMPOSITION_SCHEMA_VERSION
        and manifest.get("composition_mode") == COMPOSITION_MODE
        and isinstance(composition_id, str)
        and composition_id.startswith("local-standalone-")
        and SAFE_ID.fullmatch(composition_id) is not None
        and manifest.get("ap_group_id") is None
        and manifest.get("template") == "skillevolbench"
        and manifest.get("dataset") == expected_dataset
        and manifest.get("split") == expected_split
        and isinstance(benchmark_revision, str)
        and HEX40.fullmatch(benchmark_revision) is not None
        and isinstance(agenthub_revision, str)
        and HEX40.fullmatch(agenthub_revision) is not None
        and manifest.get("k8s_namespace") == EXPECTED_NAMESPACE
        and manifest.get("baseline_name") == expected_baseline
        and manifest.get("order_seed") == expected_order_seed
        and manifest.get("expected_environments") == expected_environment_list
        and manifest.get("source_job_count") == len(EXPECTED_ENVIRONMENTS)
        and isinstance(source_jobs, dict)
        and set(source_jobs) == set(EXPECTED_ENVIRONMENTS)
        and manifest.get("transport_metadata_policy") == "artifacts_json_excluded"
        and manifest.get("permission_policy")
        == {
            "directories": "0700",
            "regular_files": "0600",
            "symlinks": "preserved_without_following",
        }
        and manifest.get("composition_safety_scan")
        == {
            "scanner_schema_version": SAFETY_SCAN_SCHEMA_VERSION,
            "scope": "complete_composition_tree_before_atomic_publish",
            "clean": True,
            "scan_complete": True,
            "finding_count": 0,
            "artifacts_json_retained": False,
        }
        and isinstance(local_postprocess, dict)
    )
    if not manifest_structure_valid:
        context.error("composition_manifest_invalid", "group")

    group_structure_valid = (
        set(group) == expected_group_keys
        and group.get("schema_version") == COMPOSITION_SCHEMA_VERSION
        and group.get("composition_mode") == COMPOSITION_MODE
        and group.get("aggregation_origin") == "local_postprocess"
        and group.get("ap_group_id") is None
        and group.get("group_id") == composition_id
        and group.get("template") == "skillevolbench"
        and group.get("dataset") == expected_dataset
        and group.get("split") == expected_split
        and group.get("benchmark_revision") == benchmark_revision
        and group.get("template_commit") == agenthub_revision
        and group.get("k8s_namespace") == EXPECTED_NAMESPACE
        and group.get("composition_manifest") == "composition_manifest.json"
        and group.get("expected_environments") == expected_environment_list
        and isinstance(source_job_ids, dict)
        and set(source_job_ids) == set(EXPECTED_ENVIRONMENTS)
        and group.get("group_post_process_job_id") == LOCAL_POSTPROCESS_JOB_ID
        and group.get("stats") == expected_stats
    )
    if not group_structure_valid:
        context.error("local_composition_group_metadata_invalid", "group")
    if (
        expected_benchmark_revision is not None
        and benchmark_revision != expected_benchmark_revision
    ):
        context.error("benchmark_revision_mismatch", "group")
    if (
        expected_agenthub_revision is not None
        and agenthub_revision != expected_agenthub_revision
    ):
        context.error("agenthub_revision_mismatch", "group")

    if not isinstance(source_jobs, dict) or not isinstance(source_job_ids, dict):
        return

    expected_entry_keys = {
        "job_id",
        "relative_path",
        "job_metadata_sha256",
        "dataset_episode_sha256",
        "run_manifest_sha256",
        "metrics_sha256",
        "source_projected_tree",
        "copied_projected_tree",
        "source_safety_scan",
        "copied_safety_scan",
    }
    observed_job_ids: set[str] = set()
    raw_metrics: dict[str, dict[str, Any]] = {}
    validated_job_ids: dict[str, str] = {}
    source_entries_valid = True
    for environment_id in EXPECTED_ENVIRONMENTS:
        entry = source_jobs.get(environment_id)
        job_id = source_job_ids.get(environment_id)
        if not (
            isinstance(entry, dict)
            and set(entry) == expected_entry_keys
            and isinstance(job_id, str)
            and SAFE_ID.fullmatch(job_id) is not None
            and entry.get("job_id") == job_id
            and entry.get("relative_path") == f"jobs/{job_id}"
            and all(
                isinstance(entry.get(key), str)
                and HEX64.fullmatch(entry[key]) is not None
                for key in (
                    "job_metadata_sha256",
                    "dataset_episode_sha256",
                    "run_manifest_sha256",
                    "metrics_sha256",
                )
            )
            and _tree_proof_valid(entry.get("source_projected_tree"))
            and _tree_proof_valid(entry.get("copied_projected_tree"))
            and _safety_scan_proof_valid(
                entry.get("source_safety_scan"),
                require_no_transport_metadata=False,
            )
            and _safety_scan_proof_valid(
                entry.get("copied_safety_scan"),
                require_no_transport_metadata=True,
            )
        ):
            source_entries_valid = False
            continue
        source_tree = entry["source_projected_tree"]
        copied_tree = entry["copied_projected_tree"]
        source_scan_counts = entry["source_safety_scan"]["scan_counts"]
        copied_scan_counts = entry["copied_safety_scan"]["scan_counts"]
        expected_copied_tree = {
            **source_tree,
            "excluded_artifacts_json": 0,
        }
        scan_proofs_consistent = (
            copied_tree == expected_copied_tree
            and source_scan_counts["directories"] == source_tree["directories"]
            and source_scan_counts["regular_files"]
            == source_tree["regular_files"] + source_tree["excluded_artifacts_json"]
            and source_scan_counts["symlinks"] == source_tree["symlinks"]
            and source_scan_counts["bytes_scanned"] == source_tree["regular_file_bytes"]
            and source_scan_counts["skipped_artifacts_json"]
            == source_tree["excluded_artifacts_json"]
            and copied_scan_counts["directories"] == copied_tree["directories"]
            and copied_scan_counts["regular_files"] == copied_tree["regular_files"]
            and copied_scan_counts["symlinks"] == copied_tree["symlinks"]
            and copied_scan_counts["bytes_scanned"] == copied_tree["regular_file_bytes"]
        )
        if not scan_proofs_consistent:
            source_entries_valid = False
            continue
        if job_id in observed_job_ids:
            source_entries_valid = False
            continue
        observed_job_ids.add(job_id)
        validated_job_ids[environment_id] = job_id
        job_root = group_root / "jobs" / job_id
        try:
            observed_tree = summarize_projected_tree(job_root)
        except ValueError:
            context.error("composition_copied_tree_invalid", environment_id)
            continue
        if (
            observed_tree != copied_tree
            or observed_tree["excluded_artifacts_json"] != 0
        ):
            context.error("composition_copied_tree_mismatch", environment_id)
        output_root = job_root / "artifacts" / "output"
        job_path = job_root / "job.json"
        dataset_path = output_root / "dataset_episode.json"
        run_manifest_path = output_root / "ap_run_manifest.json"
        metrics_path = output_root / "metrics.json"
        if not all(
            _is_regular_beneath(job_root, path)
            for path in (job_path, dataset_path, run_manifest_path, metrics_path)
        ):
            context.error("composition_source_path_invalid", environment_id)
            continue
        job = _load_json_object(
            job_path,
            context=context,
            code="composition_job_metadata",
            scope=environment_id,
        )
        dataset = _load_json_object(
            dataset_path,
            context=context,
            code="composition_dataset_episode",
            scope=environment_id,
        )
        run_manifest = _load_json_object(
            run_manifest_path,
            context=context,
            code="composition_run_manifest",
            scope=environment_id,
        )
        metrics = _load_json_object(
            metrics_path,
            context=context,
            code="composition_metrics",
            scope=environment_id,
        )
        if job is not None and not (
            "group_id" in job
            and job["group_id"] is None
            and job.get("job_id") == job_id
            and job.get("instance_id") == environment_id
            and job.get("status") == "Succeeded"
            and job.get("k8s_namespace") == EXPECTED_NAMESPACE
            and job.get("template") == "skillevolbench"
            and job.get("agenthub_revision") == agenthub_revision
            and job.get("template_commit") == agenthub_revision
        ):
            context.error("composition_job_metadata_invalid", environment_id)
        if dataset is not None and not (
            dataset.get("schema_version") == "1.0"
            and dataset.get("dataset") == expected_dataset
            and dataset.get("split") == expected_split
            and dataset.get("instance_id") == environment_id
            and dataset.get("environment_id") == environment_id
            and dataset.get("benchmark_revision") == benchmark_revision
            and dataset.get("family_count") == FAMILIES_PER_ENVIRONMENT
            and dataset.get("primary_task_count") == PRIMARY_PER_ENVIRONMENT
            and dataset.get("roles") == [f"T{i}" for i in range(1, 7)]
            and dataset.get("scoreable_unit") == "complete_environment_episode"
        ):
            context.error("composition_dataset_episode_invalid", environment_id)
        if run_manifest is not None and not (
            run_manifest.get("schema_version") == "1.0"
            and run_manifest.get("benchmark_revision") == benchmark_revision
            and run_manifest.get("canonical") is True
            and run_manifest.get("execution_scope") == "environment"
            and run_manifest.get("environment_id") == environment_id
            and run_manifest.get("family_smoke_id") is None
            and run_manifest.get("smoke_max_tasks") is None
            and run_manifest.get("baseline_name") == expected_baseline
            and run_manifest.get("order_seed") == expected_order_seed
            and run_manifest.get("within_env_replay") is False
            and run_manifest.get("replay_eval") is False
            and isinstance(run_manifest.get("run_id"), str)
            and SAFE_ID.fullmatch(run_manifest["run_id"]) is not None
            and (metrics or {}).get("run_id") == run_manifest.get("run_id")
        ):
            context.error("composition_run_manifest_invalid", environment_id)
        if metrics is not None:
            if canonical_metric_errors(
                metrics,
                expected_environment=environment_id,
                expected_baseline=expected_baseline,
            ):
                context.error("composition_metrics_invalid", environment_id)
            raw_metrics[environment_id] = metrics

        paths_and_keys = (
            (job_path, "job_metadata_sha256"),
            (dataset_path, "dataset_episode_sha256"),
            (run_manifest_path, "run_manifest_sha256"),
            (metrics_path, "metrics_sha256"),
        )
        for path, key in paths_and_keys:
            if path.is_symlink() or not path.is_file():
                continue
            try:
                matches = _sha256_file(path) == entry[key]
            except OSError:
                matches = False
            if not matches:
                context.error("composition_source_hash_mismatch", environment_id)

    if not source_entries_valid or len(observed_job_ids) != len(EXPECTED_ENVIRONMENTS):
        context.error("composition_source_jobs_invalid", "group")

    jobs_root = group_root / "jobs"
    if not jobs_root.is_symlink() and jobs_root.is_dir():
        try:
            job_entries = list(jobs_root.iterdir())
        except OSError:
            job_entries = []
        expected_job_names = observed_job_ids | {LOCAL_POSTPROCESS_JOB_ID}
        if not (
            {entry.name for entry in job_entries} == expected_job_names
            and all(not entry.is_symlink() and entry.is_dir() for entry in job_entries)
        ):
            context.error("composition_jobs_root_invalid", "group")

    if not private_permissions_valid(group_root):
        context.error("composition_private_permissions_invalid", "group")
    try:
        observed_safety_scan = dict(scan_tree(group_root))
    except ScanError:
        context.error("composition_safety_scan_incomplete", "group")
    else:
        if not _safety_scan_proof_valid(
            observed_safety_scan,
            require_no_transport_metadata=True,
        ):
            context.error("composition_safety_scan_failed", "group")

    expected_local_postprocess = {
        "job_id": LOCAL_POSTPROCESS_JOB_ID,
        "relative_metrics_path": LOCAL_METRICS_RELATIVE_PATH,
        "aggregation_method": AGGREGATION_METHOD,
    }
    if not (
        isinstance(local_postprocess, dict)
        and set(local_postprocess) == {*expected_local_postprocess, "metrics_sha256"}
        and all(
            local_postprocess.get(key) == value
            for key, value in expected_local_postprocess.items()
        )
        and isinstance(local_postprocess.get("metrics_sha256"), str)
        and HEX64.fullmatch(local_postprocess["metrics_sha256"]) is not None
    ):
        context.error("composition_local_postprocess_invalid", "group")
        return

    local_metrics_path = group_root / LOCAL_METRICS_RELATIVE_PATH
    local_metrics = _load_json_object(
        local_metrics_path,
        context=context,
        code="composition_local_metrics",
        scope="group",
    )
    if local_metrics is None:
        return
    try:
        local_metrics_hash = _sha256_file(local_metrics_path)
    except OSError:
        local_metrics_hash = ""
    if local_metrics_hash != local_postprocess["metrics_sha256"]:
        context.error("composition_local_metrics_hash_mismatch", "group")
    if len(raw_metrics) == len(EXPECTED_ENVIRONMENTS) and len(validated_job_ids) == len(
        EXPECTED_ENVIRONMENTS
    ):
        try:
            expected_metrics = build_aggregate_metrics(
                raw_metrics,
                validated_job_ids,
                expected_baseline=expected_baseline,
            )
        except ValueError:
            context.error("composition_aggregate_input_invalid", "group")
        else:
            if local_metrics != expected_metrics:
                context.error("composition_local_aggregate_mismatch", "group")
            source_entries_for_id = {
                environment_id: source_jobs[environment_id]
                for environment_id in EXPECTED_ENVIRONMENTS
            }
            expected_composition_id = build_composition_id(
                benchmark_revision=str(benchmark_revision),
                agenthub_revision=str(agenthub_revision),
                dataset=expected_dataset,
                split=expected_split,
                source_entries=source_entries_for_id,
            )
            if composition_id != expected_composition_id:
                context.error("composition_id_mismatch", "group")


def _find_group_metrics(
    group_root: Path,
    group: dict[str, Any],
    explicit: Path | None,
    *,
    context: AuditContext,
) -> dict[str, Any] | None:
    post_job_id = group.get("group_post_process_job_id")
    if isinstance(post_job_id, str) and SAFE_ID.fullmatch(post_job_id):
        authoritative = (
            group_root / "jobs" / post_job_id / "artifacts" / "output" / "metrics.json"
        )
        # A normal AP post-process export also contains a wrapper metrics copy
        # at jobs/<id>/metrics.json.  The benchmark-owned raw artifact above is
        # authoritative and must win when both are present.
        if authoritative.exists() or authoritative.is_symlink():
            if authoritative.is_symlink() or not authoritative.is_file():
                context.error("group_post_process_metrics_invalid", "group")
                return None
            return _load_json_object(
                authoritative.resolve(strict=True),
                context=context,
                code="group_post_process_metrics",
                scope="group",
            )

    candidates: list[Path] = []
    if explicit is not None:
        candidates.append(explicit)
    if isinstance(post_job_id, str) and SAFE_ID.fullmatch(post_job_id):
        candidates.append(group_root / "jobs" / post_job_id / "metrics.json")
    candidates.extend(
        [
            group_root / "post_process" / "artifacts" / "output" / "metrics.json",
            group_root / "group_post_process" / "metrics.json",
        ]
    )
    existing = []
    for candidate in candidates:
        try:
            resolved = candidate.resolve(strict=True)
        except FileNotFoundError:
            continue
        if (
            resolved.is_file()
            and not candidate.is_symlink()
            and resolved not in existing
        ):
            existing.append(resolved)
    if len(existing) != 1:
        context.error("group_post_process_metrics_count_invalid", "group")
        return None
    return _load_json_object(
        existing[0],
        context=context,
        code="group_post_process_metrics",
        scope="group",
    )


def audit_full_group(
    group_root: Path,
    *,
    expected_benchmark_revision: str | None = None,
    expected_agenthub_revision: str | None = None,
    expected_dataset: str = EXPECTED_DATASET,
    expected_split: str = EXPECTED_SPLIT,
    expected_baseline: str = EXPECTED_BASELINE,
    expected_order_seed: str = EXPECTED_ORDER_SEED,
    group_metrics_path: Path | None = None,
) -> AuditReport:
    """Audit a local full-group export without network access or mutations."""

    root = group_root.expanduser().resolve()
    context = AuditContext()
    report = AuditReport(dataset=expected_dataset, split=expected_split)
    if not root.is_dir():
        context.error("group_root_missing", "group")
        report.errors = context.errors
        return report

    group = _load_json_object(
        root / "group.json",
        context=context,
        code="group_metadata",
        scope="group",
    )
    if group is None:
        report.errors = context.errors
        return report
    report.group_id = _safe_identifier(group.get("group_id"))
    template_commit = group.get("template_commit")
    report.agenthub_revision = _safe_identifier(template_commit)
    stats = group.get("stats")
    local_composition = group.get("composition_mode") == COMPOSITION_MODE
    if local_composition:
        report.composition_mode = COMPOSITION_MODE
        report.aggregation_origin = "local_postprocess"
        _validate_local_composition(
            root,
            group,
            expected_benchmark_revision=expected_benchmark_revision,
            expected_agenthub_revision=expected_agenthub_revision,
            expected_dataset=expected_dataset,
            expected_split=expected_split,
            expected_baseline=expected_baseline,
            expected_order_seed=expected_order_seed,
            context=context,
        )
    else:
        if group.get("composition_mode") is not None:
            context.error("composition_mode_unsupported", "group")
        # AP group stats currently stores the base dataset namespace, while some
        # older exports retained the submitted dataset-version string.  The split
        # remains authoritative in each environment's dataset_episode.json.
        accepted_group_datasets = {
            expected_dataset,
            f"{expected_dataset}/{expected_split}",
        }
        if not (
            group.get("template") == "skillevolbench"
            and group.get("dataset") in accepted_group_datasets
            and isinstance(template_commit, str)
            and HEX40.fullmatch(template_commit)
            and isinstance(group.get("group_post_process_job_id"), str)
            and SAFE_ID.fullmatch(group["group_post_process_job_id"])
            and isinstance(stats, dict)
            and stats.get("total") == len(EXPECTED_ENVIRONMENTS)
            and stats.get("finished") == len(EXPECTED_ENVIRONMENTS)
            and stats.get("succeeded") == len(EXPECTED_ENVIRONMENTS)
            and all(
                stats.get(key, 0) == 0
                for key in (
                    "failed",
                    "cancelled",
                    "pending",
                    "queued",
                    "running",
                    "scheduling",
                    "unknown",
                )
            )
        ):
            context.error("group_metadata_incomplete", "group")
        if (
            expected_agenthub_revision is not None
            and template_commit != expected_agenthub_revision
        ):
            context.error("agenthub_revision_mismatch", "group")

    discovered = _discover_environment_outputs(root, context=context)
    report.observed_environments = sorted(discovered)
    if set(discovered) != set(EXPECTED_ENVIRONMENTS):
        context.error("environment_set_incomplete", "group")
    if any(len(paths) != 1 for paths in discovered.values()):
        context.error("environment_output_count_invalid", "group")

    for environment_id in EXPECTED_ENVIRONMENTS:
        paths = discovered.get(environment_id, [])
        if len(paths) != 1:
            continue
        summary = _audit_environment(
            paths[0],
            expected_environment=environment_id,
            expected_dataset=expected_dataset,
            expected_split=expected_split,
            expected_baseline=expected_baseline,
            expected_order_seed=expected_order_seed,
        )
        report.environments[environment_id] = summary
        context.errors.extend(summary.errors)

    report.selected_job_count = len(report.environments)
    report.total_primary_trials = sum(
        item.primary_trials for item in report.environments.values()
    )
    report.total_replay_trials = sum(
        item.replay_trials for item in report.environments.values()
    )
    report.total_reflection_terminal = sum(
        item.reflection_terminal for item in report.environments.values()
    )
    report.total_same_session_verified = sum(
        item.same_session_verified for item in report.environments.values()
    )
    report.reflection_transfer_pairs = sum(
        item.reflection_transfer_pairs for item in report.environments.values()
    )
    report.reflection_transitions = {
        key: sum(
            item.reflection_transitions.get(key, 0)
            for item in report.environments.values()
        )
        for key in TRANSITION_KEYS
    }
    report.reflection_by_status = {
        status: {
            "n_pairs": sum(
                item.reflection_by_status.get(status, {}).get("n_pairs", 0)
                for item in report.environments.values()
            ),
            **{
                key: sum(
                    item.reflection_by_status.get(status, {}).get(key, 0)
                    for item in report.environments.values()
                )
                for key in TRANSITION_KEYS
            },
        }
        for status in ALL_REFLECTION_STATUSES
    }
    report.revision_applied = sum(
        item.revision_applied for item in report.environments.values()
    )
    report.revision_cross_task_pairs = sum(
        item.revision_cross_task_pairs for item in report.environments.values()
    )
    report.revision_transitions = {
        key: sum(
            item.revision_transitions.get(key, 0)
            for item in report.environments.values()
        )
        for key in TRANSITION_KEYS
    }
    if (
        len(report.environments) == len(EXPECTED_ENVIRONMENTS)
        and report.reflection_transfer_pairs
        != len(EXPECTED_ENVIRONMENTS) * REFLECTIONS_PER_ENVIRONMENT
    ):
        context.error("group_reflection_transfer_pairs_invalid", "group")

    if report.environments:
        provenance_fields = (
            "benchmark_revision",
            "source_archive_sha256",
            "benchmark_hash",
            "harbor_revision",
            "model_id_sha256",
        )
        for field_name in provenance_fields:
            values = {
                getattr(summary, field_name) for summary in report.environments.values()
            }
            if len(values) != 1 or "unknown" in values:
                context.error("cross_environment_provenance_mismatch", "group")
                break
        revisions = {
            summary.benchmark_revision for summary in report.environments.values()
        }
        if len(revisions) == 1:
            report.benchmark_revision = next(iter(revisions))
    if (
        expected_benchmark_revision is not None
        and report.benchmark_revision != expected_benchmark_revision
    ):
        context.error("benchmark_revision_mismatch", "group")

    group_metrics = _find_group_metrics(
        root,
        group,
        group_metrics_path,
        context=context,
    )
    if group_metrics is not None:
        expected_environment_list = list(EXPECTED_ENVIRONMENTS)
        per_environment = group_metrics.get("per_environment")
        structure_valid = (
            group_metrics.get("status") == "completed"
            and group_metrics.get("scoreable") is True
            and group_metrics.get("expected_environments") == expected_environment_list
            and group_metrics.get("missing_environments") == []
            and group_metrics.get("incomplete_environments") == []
            and group_metrics.get("n_environments") == len(EXPECTED_ENVIRONMENTS)
            and isinstance(per_environment, dict)
            and set(per_environment) == set(EXPECTED_ENVIRONMENTS)
        )
        if not structure_valid:
            context.error("group_post_process_incomplete", "group")
        environment_copies_valid = structure_valid and all(
            isinstance(per_environment[environment_id], dict)
            and per_environment[environment_id].get("environment_id") == environment_id
            and per_environment[environment_id].get("status") == "completed"
            and per_environment[environment_id].get("scoreable") is True
            and per_environment[environment_id].get("n_primary_trials")
            == PRIMARY_PER_ENVIRONMENT
            for environment_id in EXPECTED_ENVIRONMENTS
        )
        if structure_valid and not environment_copies_valid:
            context.error("group_post_process_environment_mismatch", "group")

        raw_summaries = [
            report.environments.get(environment_id)
            for environment_id in EXPECTED_ENVIRONMENTS
        ]
        raw_metrics_complete = all(
            summary is not None
            and summary.evaluation_sr is not None
            and summary.metric_passed is not None
            for summary in raw_summaries
        )
        aggregate_valid = False
        if not raw_metrics_complete:
            context.error("group_post_process_raw_metrics_incomplete", "group")
        else:
            typed_summaries = [summary for summary in raw_summaries if summary]
            expected_evaluation_sr = math.fsum(
                summary.evaluation_sr  # type: ignore[arg-type]
                for summary in typed_summaries
            ) / len(EXPECTED_ENVIRONMENTS)
            expected_passed = all(
                summary.metric_passed is True for summary in typed_summaries
            )
            aggregate_valid = (
                _unit_interval_number(group_metrics.get("evaluation_sr"))
                and _unit_interval_number(group_metrics.get("task_score"))
                and _same_number(
                    group_metrics.get("evaluation_sr"), expected_evaluation_sr
                )
                and _same_number(
                    group_metrics.get("task_score"),
                    group_metrics.get("evaluation_sr"),
                )
                and type(group_metrics.get("passed")) is bool
                and group_metrics.get("passed") is expected_passed
            )
            if not aggregate_valid:
                context.error("group_post_process_aggregate_mismatch", "group")

        report.group_post_process_verified = bool(
            structure_valid and environment_copies_valid and aggregate_valid
        )

    report.errors = context.errors
    report.passed = not context.errors
    return report


def _render_human(report: AuditReport) -> str:
    lines = [
        f"GROUP {report.group_id}",
        f"RESULT {'PASS' if report.passed else 'FAIL'}",
        (
            "COMPOSITION "
            f"mode={report.composition_mode} "
            f"aggregation={report.aggregation_origin}"
        ),
        (
            "ENVIRONMENTS "
            f"observed={','.join(report.observed_environments) or '-'} "
            f"selected={report.selected_job_count}/6"
        ),
        (
            "TOTALS "
            f"primary={report.total_primary_trials}/180 "
            f"replay={report.total_replay_trials}/0 "
            f"reflection_terminal={report.total_reflection_terminal}/90 "
            f"same_session={report.total_same_session_verified}/90"
        ),
        (
            "PROVENANCE "
            f"benchmark={report.benchmark_revision} "
            f"agenthub={report.agenthub_revision} "
            f"dataset={report.dataset}/{report.split}"
        ),
        (
            "GROUP_POST_PROCESS "
            f"{'PASS' if report.group_post_process_verified else 'FAIL'}"
        ),
        (
            "REFLECTION_TRANSFER observational_only=true "
            f"pairs={report.reflection_transfer_pairs}/90 "
            + " ".join(
                f"{key.removesuffix('_count')}={report.reflection_transitions[key]}"
                for key in TRANSITION_KEYS
            )
        ),
        (
            "REVISION_SAFETY applied_patch_conditioned=true "
            f"applied={report.revision_applied} "
            f"pairs={report.revision_cross_task_pairs} "
            + " ".join(
                f"{key.removesuffix('_count')}={report.revision_transitions[key]}"
                for key in TRANSITION_KEYS
            )
        ),
    ]
    for environment_id in EXPECTED_ENVIRONMENTS:
        summary = report.environments.get(environment_id)
        if summary is None:
            lines.append(f"{environment_id} MISSING")
            continue
        lines.append(
            f"{environment_id} {'PASS' if summary.passed else 'FAIL'} "
            f"status={summary.status} scoreable={summary.scoreable} "
            f"primary={summary.primary_trials} replay={summary.replay_trials} "
            f"reflection={summary.reflection_terminal} "
            f"same_session={summary.same_session_verified} "
            f"manifest_changed={summary.manifest_changed_files}"
        )
    if report.errors:
        lines.append("ERRORS")
        lines.extend(f"- {item.scope}:{item.code}" for item in report.errors)
    return "\n".join(lines)


def _validate_expected_revision(value: str | None, option: str) -> str | None:
    if value is not None and HEX40.fullmatch(value) is None:
        raise argparse.ArgumentTypeError(f"{option} must be a 40-character git SHA")
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group_export", type=Path)
    parser.add_argument("--expected-dataset", default=EXPECTED_DATASET)
    parser.add_argument("--expected-split", default=EXPECTED_SPLIT)
    parser.add_argument("--expected-baseline", default=EXPECTED_BASELINE)
    parser.add_argument("--expected-order-seed", default=EXPECTED_ORDER_SEED)
    parser.add_argument("--expected-benchmark-revision")
    parser.add_argument("--expected-agenthub-revision")
    parser.add_argument(
        "--group-metrics",
        type=Path,
        help="Explicit local post-process metrics.json when exported separately",
    )
    parser.add_argument("--json", action="store_true", dest="json_output")
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(list(argv) if argv is not None else None)
    try:
        expected_benchmark_revision = _validate_expected_revision(
            args.expected_benchmark_revision,
            "--expected-benchmark-revision",
        )
        expected_agenthub_revision = _validate_expected_revision(
            args.expected_agenthub_revision,
            "--expected-agenthub-revision",
        )
    except argparse.ArgumentTypeError as exc:
        parser.error(str(exc))
    report = audit_full_group(
        args.group_export,
        expected_benchmark_revision=expected_benchmark_revision,
        expected_agenthub_revision=expected_agenthub_revision,
        expected_dataset=args.expected_dataset,
        expected_split=args.expected_split,
        expected_baseline=args.expected_baseline,
        expected_order_seed=args.expected_order_seed,
        group_metrics_path=args.group_metrics,
    )
    if args.json_output:
        print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    else:
        print(_render_human(report))
    return 0 if report.passed else 2


if __name__ == "__main__":
    raise SystemExit(main())
