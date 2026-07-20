#!/usr/bin/env python3
"""Compose six standalone AP job exports into one auditable local result.

This helper is intentionally not an AP group exporter.  It accepts exactly one
successful standalone export for each SkillEvolBench environment E1 through E6,
validates their AP and benchmark identity, copies them into a self-contained
root, and applies the same aggregation formula as Agent-Hub's
skillevolbench/group_post_process.sh.

The generated group.json and composition_manifest.json both identify the result
as a local standalone-job composition.  Input exports are never modified and an
existing output path is never overwritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import shutil
import stat
import statistics
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.ap.scan_export_safety import (  # noqa: E402
    SCHEMA_VERSION as SAFETY_SCAN_SCHEMA_VERSION,
)
from scripts.ap.scan_export_safety import ScanError, scan_tree  # noqa: E402


EXPECTED_ENVIRONMENTS = tuple(f"E{i}" for i in range(1, 7))
EXPECTED_NAMESPACE = "megaflow-benchmark-dev"
EXPECTED_TEMPLATE = "skillevolbench"
EXPECTED_DATASET = "skillevolbench/skillevolbench"
EXPECTED_BASELINE = "selfgen_in_session_always"
EXPECTED_ORDER_SEED = "A"
EXPECTED_PRIMARY_TRIALS = 30
EXPECTED_REFLECTIONS = 15
COMPOSITION_MODE = "standalone_jobs_local_aggregate"
COMPOSITION_SCHEMA_VERSION = 1
AGGREGATION_METHOD = "agenthub_skillevolbench_group_post_process_v1"
LOCAL_POSTPROCESS_JOB_ID = "local-post-process"
LOCAL_METRICS_RELATIVE_PATH = (
    f"jobs/{LOCAL_POSTPROCESS_JOB_ID}/artifacts/output/metrics.json"
)
SAFE_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.@+-]{0,199}$")
HEX40 = re.compile(r"^[0-9a-f]{40}$")


class CompositionError(ValueError):
    """A fail-closed standalone composition validation error."""


@dataclass(frozen=True)
class SourceJob:
    """Validated fields retained from one standalone AP job export."""

    source_root: Path
    environment_id: str
    job_id: str
    job: dict[str, Any]
    dataset: dict[str, Any]
    run_manifest: dict[str, Any]
    metrics: dict[str, Any]
    job_sha256: str
    dataset_sha256: str
    run_manifest_sha256: str
    metrics_sha256: str
    source_tree: dict[str, Any]
    source_safety_scan: dict[str, Any]


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-standard JSON constant: {value}")


def _load_json_object(path: Path, *, label: str) -> dict[str, Any]:
    if path.is_symlink() or not path.is_file():
        raise CompositionError(f"{label} is missing or is not a regular file")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_json_constant,
        )
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, ValueError) as error:
        raise CompositionError(f"{label} is not valid JSON") from error
    if not isinstance(value, dict):
        raise CompositionError(f"{label} must contain a JSON object")
    return value


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def summarize_projected_tree(root: Path) -> dict[str, Any]:
    """Hash a tree without following links or reading AP transport metadata."""

    if root.is_symlink() or not root.is_dir():
        raise CompositionError("tree root is not a regular directory")
    digest = hashlib.sha256()
    counts = {
        "directories": 1,
        "regular_files": 0,
        "symlinks": 0,
        "regular_file_bytes": 0,
        "excluded_artifacts_json": 0,
    }

    def update(kind: bytes, relative: Path, extra: bytes = b"") -> None:
        try:
            encoded_path = relative.as_posix().encode("utf-8")
        except UnicodeEncodeError as error:
            raise CompositionError("tree contains a non-UTF-8 path") from error
        digest.update(kind + b"\0" + encoded_path + b"\0" + extra + b"\0")

    def walk(directory: Path, relative_directory: Path) -> None:
        try:
            with os.scandir(directory) as entries:
                ordered = sorted(entries, key=lambda entry: os.fsencode(entry.name))
        except OSError as error:
            raise CompositionError("tree contains an unreadable directory") from error
        for entry in ordered:
            path = Path(entry.path)
            relative = relative_directory / entry.name
            try:
                if entry.is_symlink():
                    if entry.name == "artifacts.json":
                        raise CompositionError(
                            "artifacts.json transport metadata must be a regular file"
                        )
                    target = os.readlink(path)
                    update(b"L", relative, os.fsencode(target))
                    counts["symlinks"] += 1
                elif entry.is_dir(follow_symlinks=False):
                    if entry.name == "artifacts.json":
                        raise CompositionError(
                            "artifacts.json transport metadata must be a regular file"
                        )
                    update(b"D", relative)
                    counts["directories"] += 1
                    walk(path, relative)
                elif entry.is_file(follow_symlinks=False):
                    if entry.name == "artifacts.json":
                        counts["excluded_artifacts_json"] += 1
                        continue
                    flags = (
                        os.O_RDONLY
                        | getattr(os, "O_CLOEXEC", 0)
                        | getattr(os, "O_NOFOLLOW", 0)
                    )
                    descriptor = os.open(path, flags)
                    try:
                        file_stat = os.fstat(descriptor)
                        if not stat.S_ISREG(file_stat.st_mode):
                            raise CompositionError(
                                "tree contains an unsupported filesystem object"
                            )
                        update(b"F", relative, str(file_stat.st_size).encode("ascii"))
                        bytes_read = 0
                        while chunk := os.read(descriptor, 1024 * 1024):
                            digest.update(chunk)
                            bytes_read += len(chunk)
                        if bytes_read != file_stat.st_size:
                            raise CompositionError(
                                "tree file changed while being hashed"
                            )
                    finally:
                        os.close(descriptor)
                    counts["regular_files"] += 1
                    counts["regular_file_bytes"] += file_stat.st_size
                else:
                    raise CompositionError(
                        "tree contains an unsupported filesystem object"
                    )
            except OSError as error:
                raise CompositionError("tree cannot be hashed safely") from error

    walk(root, Path())
    return {
        "algorithm": "sha256_path_type_content_v1",
        "sha256": digest.hexdigest(),
        **counts,
    }


def _require_clean_scan(
    report: dict[str, Any],
    *,
    label: str,
    require_no_transport_metadata: bool,
) -> None:
    scan_counts = report.get("scan_counts")
    if not (
        report.get("schema_version") == SAFETY_SCAN_SCHEMA_VERSION
        and report.get("clean") is True
        and report.get("scan_complete") is True
        and report.get("finding_count") == 0
        and isinstance(scan_counts, dict)
        and (
            not require_no_transport_metadata
            or scan_counts.get("skipped_artifacts_json") == 0
        )
    ):
        raise CompositionError(f"{label} did not pass the complete safety scan")


def _normalize_private_permissions(root: Path) -> None:
    """Make copied evidence private without following preserved symlinks."""

    def walk(directory: Path) -> None:
        directory.chmod(0o700)
        try:
            with os.scandir(directory) as entries:
                ordered = list(entries)
        except OSError as error:
            raise CompositionError(
                "copied tree permissions cannot be normalized"
            ) from error
        for entry in ordered:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    walk(path)
                elif entry.is_file(follow_symlinks=False):
                    path.chmod(0o600)
                else:
                    raise CompositionError(
                        "copied tree contains an unsupported filesystem object"
                    )
            except OSError as error:
                raise CompositionError(
                    "copied tree permissions cannot be normalized"
                ) from error

    walk(root)


def private_permissions_valid(root: Path) -> bool:
    """Check the exact private permission policy without following symlinks."""

    if root.is_symlink() or not root.is_dir():
        return False

    def walk(directory: Path) -> bool:
        try:
            if directory.stat(follow_symlinks=False).st_mode & 0o7777 != 0o700:
                return False
            with os.scandir(directory) as entries:
                ordered = list(entries)
        except OSError:
            return False
        for entry in ordered:
            path = Path(entry.path)
            try:
                if entry.is_symlink():
                    continue
                if entry.is_dir(follow_symlinks=False):
                    if not walk(path):
                        return False
                elif entry.is_file(follow_symlinks=False):
                    if path.stat(follow_symlinks=False).st_mode & 0o7777 != 0o600:
                        return False
                else:
                    return False
            except OSError:
                return False
        return True

    return walk(root)


def _ignore_transport_metadata(_directory: str, names: list[str]) -> set[str]:
    """Exclude AP signed-download transport metadata from every copied job."""

    return {"artifacts.json"} if "artifacts.json" in names else set()


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


def _finite_number(value: Any) -> bool:
    return (
        isinstance(value, (int, float))
        and not isinstance(value, bool)
        and math.isfinite(float(value))
    )


def _unit_interval_number(value: Any) -> bool:
    return _finite_number(value) and 0.0 <= float(value) <= 1.0


def _exact_count(data: dict[str, Any], key: str, expected: int) -> bool:
    value = data.get(key)
    return type(value) is int and value == expected


def canonical_metric_errors(
    data: dict[str, Any],
    *,
    expected_environment: str,
    expected_baseline: str,
) -> list[str]:
    """Return field names that violate Agent-Hub's canonical metric checks."""

    errors: list[str] = []
    exact_values: dict[str, Any] = {
        "scoreable": True,
        "status": "completed",
        "canonical": True,
        "execution_scope": "environment",
        "environment_id": expected_environment,
        "family_smoke_id": None,
        "baseline_name": expected_baseline,
        "reflection_enabled": True,
    }
    for key, expected in exact_values.items():
        value = data.get(key)
        matches = (
            value is expected
            if expected is None or isinstance(expected, bool)
            else value == expected
        )
        if not matches:
            errors.append(key)

    expected_counts = {
        "n_primary_trials": EXPECTED_PRIMARY_TRIALS,
        "expected_primary_trials": EXPECTED_PRIMARY_TRIALS,
        "n_replay_trials": 0,
        "expected_replay_trials": 0,
        "n_shadow_trials": 0,
        "expected_shadow_trials": 0,
        "n_verifier_backed_trials": EXPECTED_PRIMARY_TRIALS,
        "expected_verifier_backed_trials": EXPECTED_PRIMARY_TRIALS,
        "n_reflection_expected": EXPECTED_REFLECTIONS,
        "n_reflection_attempted": EXPECTED_REFLECTIONS,
        "n_reflection_terminal": EXPECTED_REFLECTIONS,
        "n_same_session_verified": EXPECTED_REFLECTIONS,
    }
    for key, expected in expected_counts.items():
        if not _exact_count(data, key, expected):
            errors.append(key)

    evaluation_sr = data.get("evaluation_sr")
    if not _unit_interval_number(evaluation_sr):
        errors.append("evaluation_sr")
    task_score = data.get("task_score")
    if not _unit_interval_number(task_score) or task_score != evaluation_sr:
        errors.append("task_score")
    passed = data.get("passed")
    if type(passed) is not bool or (
        _unit_interval_number(evaluation_sr)
        and passed is not (float(evaluation_sr) == 1.0)
    ):
        errors.append("passed")
    return errors


def _numeric_values(
    metrics_by_environment: dict[str, dict[str, Any]], key: str
) -> list[float]:
    values: list[float] = []
    for environment_id in EXPECTED_ENVIRONMENTS:
        value = metrics_by_environment[environment_id].get(key)
        if _finite_number(value):
            values.append(float(value))
    return values


def _macro_mean(
    metrics_by_environment: dict[str, dict[str, Any]], key: str
) -> float | None:
    values = _numeric_values(metrics_by_environment, key)
    return statistics.mean(values) if values else None


def _nonnegative_count(value: Any) -> int:
    return value if type(value) is int and value >= 0 else 0


def build_aggregate_metrics(
    metrics_by_environment: dict[str, dict[str, Any]],
    job_ids_by_environment: dict[str, str],
    *,
    expected_baseline: str = EXPECTED_BASELINE,
) -> dict[str, Any]:
    """Apply Agent-Hub's group post-process formula to six validated jobs."""

    if set(metrics_by_environment) != set(EXPECTED_ENVIRONMENTS):
        raise CompositionError(
            "aggregate input must contain E1 through E6 exactly once"
        )
    if set(job_ids_by_environment) != set(EXPECTED_ENVIRONMENTS):
        raise CompositionError(
            "aggregate job IDs must contain E1 through E6 exactly once"
        )
    for environment_id in EXPECTED_ENVIRONMENTS:
        if canonical_metric_errors(
            metrics_by_environment[environment_id],
            expected_environment=environment_id,
            expected_baseline=expected_baseline,
        ):
            raise CompositionError(
                f"{environment_id}: aggregate input is not a canonical complete metric"
            )

    baseline_names = sorted(
        {
            data.get("baseline_name")
            for data in metrics_by_environment.values()
            if isinstance(data.get("baseline_name"), str)
        }
    )
    baseline_consistent = len(baseline_names) <= 1
    complete = baseline_consistent and baseline_names == [expected_baseline]
    evaluation_sr = _macro_mean(metrics_by_environment, "evaluation_sr")

    result: dict[str, Any] = {
        "task_score": evaluation_sr if complete and evaluation_sr is not None else 0.0,
        "passed": bool(
            complete
            and all(
                metrics_by_environment[environment_id].get("passed") is True
                for environment_id in EXPECTED_ENVIRONMENTS
            )
        ),
        "status": "completed" if complete else "incomplete",
        "scoreable": complete,
        "expected_environments": list(EXPECTED_ENVIRONMENTS),
        "missing_environments": [],
        "incomplete_environments": [],
        "n_environments": len(metrics_by_environment),
        "n_valid_environments": len(metrics_by_environment),
        "expected_baseline_name": expected_baseline,
        "baseline_names": baseline_names,
        "baseline_consistent": baseline_consistent,
        "candidate_counts": {
            environment_id: 1 for environment_id in EXPECTED_ENVIRONMENTS
        },
        "valid_candidate_counts": {
            environment_id: 1 for environment_id in EXPECTED_ENVIRONMENTS
        },
        "invalid_candidate_counts": {
            environment_id: 0 for environment_id in EXPECTED_ENVIRONMENTS
        },
        "selected_job_ids": {
            environment_id: job_ids_by_environment[environment_id]
            for environment_id in EXPECTED_ENVIRONMENTS
        },
        "selected_validation_errors": {},
        "evaluation_sr": evaluation_sr,
        "learning_sr": _macro_mean(metrics_by_environment, "learning_sr"),
        "t4_transfer": _macro_mean(metrics_by_environment, "t4_transfer"),
        "t5_trap_resistance": _macro_mean(metrics_by_environment, "t5_trap_resistance"),
        "t6_composition_rate": _macro_mean(
            metrics_by_environment, "t6_composition_rate"
        ),
        "evolution_lift_macro": _macro_mean(metrics_by_environment, "evolution_lift"),
        "recovery_rate_macro": _macro_mean(metrics_by_environment, "recovery_rate"),
        "regression_rate_macro": _macro_mean(metrics_by_environment, "regression_rate"),
        "cross_task_failure_recovery_rate_macro": _macro_mean(
            metrics_by_environment, "cross_task_failure_recovery_rate"
        ),
        "cross_task_success_regression_rate_macro": _macro_mean(
            metrics_by_environment, "cross_task_success_regression_rate"
        ),
        "fail_to_success_count": sum(
            _nonnegative_count(
                metrics_by_environment[environment_id].get("fail_to_success_count", 0)
            )
            for environment_id in EXPECTED_ENVIRONMENTS
        ),
        "success_to_fail_count": sum(
            _nonnegative_count(
                metrics_by_environment[environment_id].get("success_to_fail_count", 0)
            )
            for environment_id in EXPECTED_ENVIRONMENTS
        ),
        "cross_task_fail_to_success_count": sum(
            _nonnegative_count(
                metrics_by_environment[environment_id].get(
                    "cross_task_fail_to_success_count", 0
                )
            )
            for environment_id in EXPECTED_ENVIRONMENTS
        ),
        "cross_task_success_to_fail_count": sum(
            _nonnegative_count(
                metrics_by_environment[environment_id].get(
                    "cross_task_success_to_fail_count", 0
                )
            )
            for environment_id in EXPECTED_ENVIRONMENTS
        ),
        "per_environment": {
            environment_id: metrics_by_environment[environment_id]
            for environment_id in EXPECTED_ENVIRONMENTS
        },
    }
    if not complete:
        result["message"] = (
            "A benchmark-level score requires one complete, scoreable episode for "
            "each of E1..E6. Partial/smoke jobs are never promoted to a score."
        )
    return result


def _validate_source_job(
    source_root: Path,
    *,
    ordinal: int,
    expected_benchmark_revision: str,
    expected_agenthub_revision: str,
    expected_dataset: str,
    expected_split: str,
    expected_baseline: str,
    expected_order_seed: str,
) -> SourceJob:
    label = f"input-{ordinal}"
    if source_root.is_symlink() or not source_root.is_dir():
        raise CompositionError(f"{label} is missing or is not a regular directory")
    job_path = source_root / "job.json"
    output = source_root / "artifacts" / "output"
    dataset_path = output / "dataset_episode.json"
    run_manifest_path = output / "ap_run_manifest.json"
    metrics_path = output / "metrics.json"
    for name, path in (
        ("job metadata", job_path),
        ("dataset episode", dataset_path),
        ("run manifest", run_manifest_path),
        ("metrics", metrics_path),
    ):
        if not _is_regular_beneath(source_root, path):
            raise CompositionError(f"{label} {name} path is not safely contained")
    job = _load_json_object(job_path, label=f"{label} job metadata")
    dataset = _load_json_object(dataset_path, label=f"{label} dataset episode")
    run_manifest = _load_json_object(run_manifest_path, label=f"{label} run manifest")
    metrics = _load_json_object(metrics_path, label=f"{label} metrics")

    environment_id = job.get("instance_id")
    if environment_id not in EXPECTED_ENVIRONMENTS:
        raise CompositionError(f"{label}: AP instance_id is not one of E1 through E6")
    environment_id = str(environment_id)
    job_id = job.get("job_id")
    if not isinstance(job_id, str) or SAFE_ID.fullmatch(job_id) is None:
        raise CompositionError(f"{environment_id}: AP job_id is missing or unsafe")
    if not (
        "group_id" in job
        and job["group_id"] is None
        and job.get("status") == "Succeeded"
        and job.get("k8s_namespace") == EXPECTED_NAMESPACE
        and job.get("template") == EXPECTED_TEMPLATE
        and job.get("agenthub_revision") == expected_agenthub_revision
        and job.get("template_commit") == expected_agenthub_revision
    ):
        raise CompositionError(
            f"{environment_id}: AP job metadata is not a successful standalone job"
        )

    if not (
        dataset.get("schema_version") == "1.0"
        and dataset.get("dataset") == expected_dataset
        and dataset.get("split") == expected_split
        and dataset.get("instance_id") == environment_id
        and dataset.get("environment_id") == environment_id
        and dataset.get("benchmark_revision") == expected_benchmark_revision
        and dataset.get("family_count") == 5
        and dataset.get("primary_task_count") == EXPECTED_PRIMARY_TRIALS
        and dataset.get("roles") == [f"T{i}" for i in range(1, 7)]
        and dataset.get("scoreable_unit") == "complete_environment_episode"
    ):
        raise CompositionError(f"{environment_id}: dataset provenance is not canonical")

    run_id = run_manifest.get("run_id")
    if not (
        run_manifest.get("schema_version") == "1.0"
        and run_manifest.get("benchmark_revision") == expected_benchmark_revision
        and run_manifest.get("canonical") is True
        and run_manifest.get("execution_scope") == "environment"
        and run_manifest.get("environment_id") == environment_id
        and run_manifest.get("family_smoke_id") is None
        and run_manifest.get("smoke_max_tasks") is None
        and run_manifest.get("baseline_name") == expected_baseline
        and run_manifest.get("order_seed") == expected_order_seed
        and run_manifest.get("within_env_replay") is False
        and run_manifest.get("replay_eval") is False
        and isinstance(run_id, str)
        and SAFE_ID.fullmatch(run_id) is not None
        and metrics.get("run_id") == run_id
    ):
        raise CompositionError(f"{environment_id}: run manifest is not canonical")

    metric_errors = canonical_metric_errors(
        metrics,
        expected_environment=environment_id,
        expected_baseline=expected_baseline,
    )
    if metric_errors:
        raise CompositionError(
            f"{environment_id}: metrics are not canonical and complete"
        )

    try:
        source_safety_scan = dict(scan_tree(source_root))
    except ScanError as error:
        raise CompositionError(
            f"{environment_id}: source export safety scan could not complete"
        ) from error
    _require_clean_scan(
        source_safety_scan,
        label=f"{environment_id} source export",
        require_no_transport_metadata=False,
    )
    source_tree = summarize_projected_tree(source_root)

    return SourceJob(
        source_root=source_root,
        environment_id=environment_id,
        job_id=job_id,
        job=job,
        dataset=dataset,
        run_manifest=run_manifest,
        metrics=metrics,
        job_sha256=_sha256_file(job_path),
        dataset_sha256=_sha256_file(dataset_path),
        run_manifest_sha256=_sha256_file(run_manifest_path),
        metrics_sha256=_sha256_file(metrics_path),
        source_tree=source_tree,
        source_safety_scan=source_safety_scan,
    )


def _write_json(path: Path, value: dict[str, Any]) -> None:
    payload = (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            allow_nan=False,
        )
        + "\n"
    )
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with path.open("x", encoding="utf-8") as stream:
        stream.write(payload)
    path.chmod(0o600)


def _source_manifest_entry(
    source: SourceJob,
    *,
    copied_tree: dict[str, Any],
    copied_safety_scan: dict[str, Any],
) -> dict[str, Any]:
    return {
        "job_id": source.job_id,
        "relative_path": f"jobs/{source.job_id}",
        "job_metadata_sha256": source.job_sha256,
        "dataset_episode_sha256": source.dataset_sha256,
        "run_manifest_sha256": source.run_manifest_sha256,
        "metrics_sha256": source.metrics_sha256,
        "source_projected_tree": source.source_tree,
        "copied_projected_tree": copied_tree,
        "source_safety_scan": source.source_safety_scan,
        "copied_safety_scan": copied_safety_scan,
    }


def build_composition_id(
    *,
    benchmark_revision: str,
    agenthub_revision: str,
    dataset: str,
    split: str,
    source_entries: dict[str, dict[str, Any]],
) -> str:
    stable_keys = (
        "job_id",
        "job_metadata_sha256",
        "dataset_episode_sha256",
        "run_manifest_sha256",
        "metrics_sha256",
        "source_projected_tree",
    )
    stable_source_entries = {
        environment_id: {
            key: source_entries[environment_id][key] for key in stable_keys
        }
        for environment_id in EXPECTED_ENVIRONMENTS
    }
    identity = {
        "benchmark_revision": benchmark_revision,
        "agenthub_revision": agenthub_revision,
        "dataset": dataset,
        "split": split,
        "source_jobs": stable_source_entries,
    }
    encoded = json.dumps(identity, sort_keys=True, separators=(",", ":")).encode()
    return f"local-standalone-{hashlib.sha256(encoded).hexdigest()[:24]}"


def compose_standalone_full(
    job_export_dirs: Iterable[Path],
    *,
    output_root: Path,
    expected_benchmark_revision: str,
    expected_agenthub_revision: str,
    expected_dataset: str = EXPECTED_DATASET,
    expected_split: str,
    expected_baseline: str = EXPECTED_BASELINE,
    expected_order_seed: str = EXPECTED_ORDER_SEED,
) -> Path:
    """Validate and atomically compose six standalone job exports."""

    if HEX40.fullmatch(expected_benchmark_revision) is None:
        raise CompositionError("expected benchmark revision must be a 40-character SHA")
    if HEX40.fullmatch(expected_agenthub_revision) is None:
        raise CompositionError("expected Agent-Hub revision must be a 40-character SHA")
    if not expected_dataset or not expected_split:
        raise CompositionError("expected dataset and split must be non-empty")

    raw_inputs = [Path(value).expanduser() for value in job_export_dirs]
    if len(raw_inputs) != len(EXPECTED_ENVIRONMENTS):
        raise CompositionError("exactly six standalone AP job exports are required")

    resolved_inputs: list[Path] = []
    for ordinal, source in enumerate(raw_inputs, start=1):
        if source.is_symlink() or not source.is_dir():
            raise CompositionError(
                f"input-{ordinal} is missing or is not a regular directory"
            )
        resolved_inputs.append(source.resolve(strict=True))
    if len(set(resolved_inputs)) != len(resolved_inputs):
        raise CompositionError("standalone AP job export directories must be unique")

    output = output_root.expanduser().resolve(strict=False)
    if output.exists() or output.is_symlink():
        raise CompositionError("output root already exists")
    parent = output.parent
    if parent.is_symlink() or not parent.is_dir():
        raise CompositionError(
            "output root parent must be an existing regular directory"
        )
    for source in resolved_inputs:
        if (
            output == source
            or output.is_relative_to(source)
            or source.is_relative_to(output)
        ):
            raise CompositionError("output root and input exports must not overlap")

    sources = [
        _validate_source_job(
            source,
            ordinal=ordinal,
            expected_benchmark_revision=expected_benchmark_revision,
            expected_agenthub_revision=expected_agenthub_revision,
            expected_dataset=expected_dataset,
            expected_split=expected_split,
            expected_baseline=expected_baseline,
            expected_order_seed=expected_order_seed,
        )
        for ordinal, source in enumerate(resolved_inputs, start=1)
    ]
    by_environment = {source.environment_id: source for source in sources}
    if set(by_environment) != set(EXPECTED_ENVIRONMENTS) or len(by_environment) != 6:
        raise CompositionError(
            "standalone jobs must contain E1 through E6 exactly once"
        )
    if len({source.job_id for source in sources}) != len(sources):
        raise CompositionError("standalone AP job IDs must be unique")
    if LOCAL_POSTPROCESS_JOB_ID in {source.job_id for source in sources}:
        raise CompositionError("standalone AP job ID collides with local post-process")

    ordered = [
        by_environment[environment_id] for environment_id in EXPECTED_ENVIRONMENTS
    ]
    metrics_by_environment = {
        source.environment_id: source.metrics for source in ordered
    }
    job_ids_by_environment = {
        source.environment_id: source.job_id for source in ordered
    }
    aggregate = build_aggregate_metrics(
        metrics_by_environment,
        job_ids_by_environment,
        expected_baseline=expected_baseline,
    )

    staging = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=parent)).resolve(
        strict=True
    )
    staging.chmod(0o700)
    try:
        jobs_root = staging / "jobs"
        jobs_root.mkdir(mode=0o700)
        copied_proofs: dict[str, tuple[dict[str, Any], dict[str, Any]]] = {}
        for source in ordered:
            destination = jobs_root / source.job_id
            shutil.copytree(
                source.source_root,
                destination,
                symlinks=True,
                ignore=_ignore_transport_metadata,
                copy_function=shutil.copyfile,
            )
            _normalize_private_permissions(destination)
            copied_tree = summarize_projected_tree(destination)
            expected_copied_tree = {
                **source.source_tree,
                "excluded_artifacts_json": 0,
            }
            if copied_tree != expected_copied_tree:
                raise CompositionError(
                    f"{source.environment_id}: copied full-tree digest mismatch"
                )
            try:
                copied_safety_scan = dict(scan_tree(destination))
            except ScanError as error:
                raise CompositionError(
                    f"{source.environment_id}: copied tree safety scan could not complete"
                ) from error
            _require_clean_scan(
                copied_safety_scan,
                label=f"{source.environment_id} copied export",
                require_no_transport_metadata=True,
            )
            if not private_permissions_valid(destination):
                raise CompositionError(
                    f"{source.environment_id}: copied tree permissions are not private"
                )
            copied_proofs[source.environment_id] = (
                copied_tree,
                copied_safety_scan,
            )
            copied_paths = {
                "job metadata": (destination / "job.json", source.job_sha256),
                "dataset episode": (
                    destination / "artifacts" / "output" / "dataset_episode.json",
                    source.dataset_sha256,
                ),
                "run manifest": (
                    destination / "artifacts" / "output" / "ap_run_manifest.json",
                    source.run_manifest_sha256,
                ),
                "metrics": (
                    destination / "artifacts" / "output" / "metrics.json",
                    source.metrics_sha256,
                ),
            }
            for label, (path, expected_hash) in copied_paths.items():
                if not _is_regular_beneath(destination, path):
                    raise CompositionError(
                        f"{source.environment_id}: copied {label} is not regular"
                    )
                if _sha256_file(path) != expected_hash:
                    raise CompositionError(
                        f"{source.environment_id}: source changed while it was copied"
                    )

        source_entries = {
            source.environment_id: _source_manifest_entry(
                source,
                copied_tree=copied_proofs[source.environment_id][0],
                copied_safety_scan=copied_proofs[source.environment_id][1],
            )
            for source in ordered
        }
        composition_id = build_composition_id(
            benchmark_revision=expected_benchmark_revision,
            agenthub_revision=expected_agenthub_revision,
            dataset=expected_dataset,
            split=expected_split,
            source_entries=source_entries,
        )

        local_metrics_path = staging / LOCAL_METRICS_RELATIVE_PATH
        _write_json(local_metrics_path, aggregate)
        aggregate_sha256 = _sha256_file(local_metrics_path)
        manifest = {
            "schema_version": COMPOSITION_SCHEMA_VERSION,
            "composition_mode": COMPOSITION_MODE,
            "composition_id": composition_id,
            "ap_group_id": None,
            "template": EXPECTED_TEMPLATE,
            "dataset": expected_dataset,
            "split": expected_split,
            "benchmark_revision": expected_benchmark_revision,
            "agenthub_revision": expected_agenthub_revision,
            "k8s_namespace": EXPECTED_NAMESPACE,
            "baseline_name": expected_baseline,
            "order_seed": expected_order_seed,
            "expected_environments": list(EXPECTED_ENVIRONMENTS),
            "source_job_count": len(EXPECTED_ENVIRONMENTS),
            "source_jobs": source_entries,
            "transport_metadata_policy": "artifacts_json_excluded",
            "permission_policy": {
                "directories": "0700",
                "regular_files": "0600",
                "symlinks": "preserved_without_following",
            },
            "composition_safety_scan": {
                "scanner_schema_version": SAFETY_SCAN_SCHEMA_VERSION,
                "scope": "complete_composition_tree_before_atomic_publish",
                "clean": True,
                "scan_complete": True,
                "finding_count": 0,
                "artifacts_json_retained": False,
            },
            "local_postprocess": {
                "job_id": LOCAL_POSTPROCESS_JOB_ID,
                "relative_metrics_path": LOCAL_METRICS_RELATIVE_PATH,
                "aggregation_method": AGGREGATION_METHOD,
                "metrics_sha256": aggregate_sha256,
            },
        }
        _write_json(staging / "composition_manifest.json", manifest)
        group = {
            "schema_version": COMPOSITION_SCHEMA_VERSION,
            "composition_mode": COMPOSITION_MODE,
            "aggregation_origin": "local_postprocess",
            "ap_group_id": None,
            "group_id": composition_id,
            "template": EXPECTED_TEMPLATE,
            "dataset": expected_dataset,
            "split": expected_split,
            "benchmark_revision": expected_benchmark_revision,
            "template_commit": expected_agenthub_revision,
            "k8s_namespace": EXPECTED_NAMESPACE,
            "composition_manifest": "composition_manifest.json",
            "expected_environments": list(EXPECTED_ENVIRONMENTS),
            "source_job_ids": job_ids_by_environment,
            "group_post_process_job_id": LOCAL_POSTPROCESS_JOB_ID,
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
        }
        _write_json(staging / "group.json", group)
        _normalize_private_permissions(staging)
        if not private_permissions_valid(staging):
            raise CompositionError("composition tree permissions are not private")
        try:
            composition_safety_scan = dict(scan_tree(staging))
        except ScanError as error:
            raise CompositionError(
                "complete composition safety scan could not finish"
            ) from error
        _require_clean_scan(
            composition_safety_scan,
            label="complete composition tree",
            require_no_transport_metadata=True,
        )
        if output.exists() or output.is_symlink():
            raise CompositionError("output root appeared while composing")
        os.rename(staging, output)
    except BaseException:
        if staging.exists():
            shutil.rmtree(staging)
        raise
    return output


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("job_exports", nargs=6, type=Path)
    parser.add_argument("--output-root", required=True, type=Path)
    parser.add_argument("--expected-benchmark-revision", required=True)
    parser.add_argument("--expected-agenthub-revision", required=True)
    parser.add_argument("--expected-dataset", default=EXPECTED_DATASET)
    parser.add_argument("--expected-split", required=True)
    parser.add_argument("--expected-baseline", default=EXPECTED_BASELINE)
    parser.add_argument("--expected-order-seed", default=EXPECTED_ORDER_SEED)
    return parser


def main(argv: Iterable[str] | None = None) -> int:
    args = _parser().parse_args(list(argv) if argv is not None else None)
    try:
        output = compose_standalone_full(
            args.job_exports,
            output_root=args.output_root,
            expected_benchmark_revision=args.expected_benchmark_revision,
            expected_agenthub_revision=args.expected_agenthub_revision,
            expected_dataset=args.expected_dataset,
            expected_split=args.expected_split,
            expected_baseline=args.expected_baseline,
            expected_order_seed=args.expected_order_seed,
        )
    except (CompositionError, OSError) as error:
        print(f"ERROR: {error}", file=sys.stderr)
        return 2
    print(json.dumps({"composition_root": str(output), "status": "completed"}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
