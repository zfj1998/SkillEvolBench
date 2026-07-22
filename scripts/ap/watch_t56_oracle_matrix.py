#!/usr/bin/env python3
"""Durably advance the matched T4-T6 skill-condition AP matrix.

This state machine is intentionally fail-closed: no full diagnostic is
submitted until the exported E2 exact-oracle smoke passes the structural
validator.  Per-model conditions are serialized to protect model endpoints.
The curated-all condition uses the same five curated environment skills as
exact-oracle without exposing the annotated task-specific subset.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


TERMINAL = {"Succeeded", "Failed", "Cancelled"}
AGENTHUB_REF = "2dae59b5340774a528be443840b889452c78cfba"
SELFGEN_AGENTHUB_REF = "a32ea0ecd2daf6661dd3212d973d0f8e222f3a77"
FABLE_SMOKE_JOB_ID = "ap-skillevolbench-3be14e2ba69944b4-d2"
FABLE_E4_LABEL = "sig-fable-e4-repair-v1-15"
MAX_FABLE_E4_REPAIR_JOBS = 3
FABLE_E4_RETRY_BACKOFF_SEC = 300
MAX_STAGE_GROUP_JOBS = 3
STAGE_RETRY_BACKOFF_SEC = 300
STAGE_NAMES = (
    "fable_exact_oracle",
    "fable_no_skill",
    "fable_curated_all",
    "qwen_exact_oracle",
    "qwen_no_skill",
    "qwen_curated_all",
)
DEFAULT_ROOT = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_t56_oracle_study_20260723"
)
FABLE_ENDPOINTS = (
    "http://10.101.225.211:22001/v1",
    "http://10.101.224.230:22001/v1",
)


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.chmod(temporary, 0o600)
    temporary.replace(path)


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return default


def find_group_id(value: Any) -> str | None:
    if isinstance(value, str) and value.startswith("group-"):
        return value
    if isinstance(value, dict):
        direct = value.get("group_id")
        if isinstance(direct, str) and direct.startswith("group-"):
            return direct
        for child in value.values():
            found = find_group_id(child)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_group_id(child)
            if found:
                return found
    return None


def find_job_id(value: Any, instance_id: str) -> str | None:
    if isinstance(value, dict):
        direct = value.get("job_id")
        if (
            isinstance(direct, str)
            and direct.startswith("ap-")
            and value.get("instance_id") == instance_id
        ):
            return direct
        for child in value.values():
            found = find_job_id(child, instance_id)
            if found:
                return found
    if isinstance(value, list):
        for child in value:
            found = find_job_id(child, instance_id)
            if found:
                return found
    return None


def json_values(text: str) -> Iterable[Any]:
    decoder = json.JSONDecoder()
    for index, character in enumerate(text):
        if character not in "[{":
            continue
        try:
            value, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        yield value


class MatrixWatcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.root = args.study_root.resolve()
        self.state_dir = self.root / "matrix-watcher"
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.state_path = self.state_dir / "state.json"
        self.events_path = self.state_dir / "events.jsonl"
        self.inventory_path = self.root / "watcher/inventory.json"
        self.smoke_validation_path = self.root / "watcher/oracle-smoke-validation.json"
        self.repo = args.repo_root.resolve()
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        if not self.environment.get("AP_API_KEY"):
            raise RuntimeError("AP_API_KEY is required")
        self.secrets = [
            value
            for name, value in self.environment.items()
            if ("KEY" in name or "SECRET" in name or "TOKEN" in name) and len(value) >= 8
        ]
        self.state = self.load_state()

    def redact(self, value: str) -> str:
        for secret in self.secrets:
            value = value.replace(secret, "[REDACTED]")
        return value

    def load_state(self) -> dict[str, Any]:
        state = read_json(self.state_path, {})
        if isinstance(state, dict) and state.get("schema_version") == 1:
            stages = state.setdefault("stages", {})
            for name in STAGE_NAMES:
                stage = stages.setdefault(
                    name,
                    {
                        "status": "pending",
                        "idempotency_key": str(uuid.uuid4()),
                        "group_id": None,
                        "failed_groups": [],
                    },
                )
                stage.setdefault("failed_groups", [])
                stage.setdefault("max_groups", MAX_STAGE_GROUP_JOBS)
            state.setdefault(
                "fable_e4_repair",
                {
                    "status": "pending",
                    "idempotency_key": str(uuid.uuid4()),
                    "job_id": None,
                    "failed_jobs": [],
                },
            )
            repair = state["fable_e4_repair"]
            repair.setdefault("failed_jobs", [])
            repair.setdefault("max_jobs", MAX_FABLE_E4_REPAIR_JOBS)
            atomic_json(self.state_path, state)
            return state
        stages = {}
        for name in STAGE_NAMES:
            stages[name] = {
                "status": "pending",
                "idempotency_key": str(uuid.uuid4()),
                "group_id": None,
                "failed_groups": [],
                "max_groups": MAX_STAGE_GROUP_JOBS,
            }
        state = {
            "schema_version": 1,
            "created_at_utc": utc_now(),
            "fable_e4_repair": {
                "status": "pending",
                "idempotency_key": str(uuid.uuid4()),
                "job_id": None,
                "failed_jobs": [],
                "max_jobs": MAX_FABLE_E4_REPAIR_JOBS,
            },
            "stages": stages,
        }
        atomic_json(self.state_path, state)
        return state

    def save(self) -> None:
        self.state["updated_at_utc"] = utc_now()
        atomic_json(self.state_path, self.state)

    def event(self, name: str, **fields: Any) -> None:
        line = self.redact(json.dumps({"timestamp_utc": utc_now(), "event": name, **fields}, ensure_ascii=False))
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")
        os.chmod(self.events_path, 0o600)

    def heartbeat(self, phase: str, **fields: Any) -> None:
        atomic_json(
            self.state_dir / "heartbeat.json",
            {
                "updated_at_utc": utc_now(),
                "status": "active",
                "phase": phase,
                "pid": os.getpid(),
                "stages": {
                    name: {
                        "status": stage.get("status"),
                        "group_id": stage.get("group_id"),
                    }
                    for name, stage in self.state["stages"].items()
                },
                "fable_e4_repair": {
                    "status": self.state["fable_e4_repair"].get("status"),
                    "job_id": self.state["fable_e4_repair"].get("job_id"),
                    "failed_job_count": len(
                        self.state["fable_e4_repair"].get("failed_jobs", [])
                    ),
                },
                **fields,
            },
        )

    def run(self, command: list[str], *, env: dict[str, str] | None = None, timeout: int = 300) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=self.repo,
            env=env or self.environment,
            text=True,
            capture_output=True,
            timeout=timeout,
            check=False,
        )
        return subprocess.CompletedProcess(
            command,
            completed.returncode,
            self.redact(completed.stdout),
            self.redact(completed.stderr),
        )

    def group_jobs(self, group_id: str) -> list[dict[str, Any]]:
        result = self.run(
            [self.args.ap_cli, "job", "list", "--group-id", group_id, "--format", "json", "--limit", "100"],
            timeout=120,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        value = json.loads(result.stdout)
        jobs = value.get("jobs", []) if isinstance(value, dict) else []
        return [job for job in jobs if isinstance(job, dict) and job.get("job_type", "default") == "default"]

    def get_job(self, job_id: str) -> dict[str, Any]:
        result = self.run([self.args.ap_cli, "job", "get", job_id], timeout=120)
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())
        value = json.loads(result.stdout)
        if not isinstance(value, dict) or value.get("job_id") != job_id:
            raise RuntimeError(f"unexpected AP job response for {job_id}")
        return value

    def update_submitted_stages(self) -> None:
        for name, stage in self.state["stages"].items():
            group_id = stage.get("group_id")
            if not group_id:
                continue
            if stage.get("registered_with_evidence_watcher") is not True:
                self.register_group(name, str(group_id))
            jobs = self.group_jobs(str(group_id))
            statuses = [str(job.get("status") or "Unknown") for job in jobs]
            stage["job_statuses"] = {status: statuses.count(status) for status in sorted(set(statuses))}
            if len(jobs) == 6 and all(status in TERMINAL for status in statuses):
                if all(status == "Succeeded" for status in statuses):
                    if stage.get("status") != "succeeded":
                        stage["status"] = "succeeded"
                        stage["terminal_at_utc"] = utc_now()
                        self.event(
                            "group_terminal",
                            stage=name,
                            group_id=group_id,
                            status="succeeded",
                            job_statuses=stage["job_statuses"],
                        )
                    continue

                failures = stage.setdefault("failed_groups", [])
                if not isinstance(failures, list):
                    failures = []
                    stage["failed_groups"] = failures
                known_ids = {
                    str(item.get("group_id"))
                    for item in failures
                    if isinstance(item, dict) and item.get("group_id")
                }
                if str(group_id) not in known_ids:
                    failures.append(
                        {
                            "group_id": str(group_id),
                            "job_statuses": dict(stage["job_statuses"]),
                            "observed_at_utc": utc_now(),
                            "idempotency_key": stage.get("idempotency_key"),
                        }
                    )
                if len(failures) >= MAX_STAGE_GROUP_JOBS:
                    stage["status"] = "repair_exhausted"
                    stage["repair_exhausted"] = True
                    stage["terminal_at_utc"] = utc_now()
                    self.event(
                        "group_repair_exhausted",
                        stage=name,
                        group_id=group_id,
                        failed_group_count=len(failures),
                        job_statuses=stage["job_statuses"],
                    )
                    continue

                stage.update(
                    {
                        "status": "retry_backoff",
                        "group_id": None,
                        "registered_with_evidence_watcher": False,
                        "idempotency_key": str(uuid.uuid4()),
                        "next_submit_attempt_epoch": (
                            time.time() + STAGE_RETRY_BACKOFF_SEC
                        ),
                        "last_failed_group_id": str(group_id),
                    }
                )
                stage.pop("submitted_at_utc", None)
                stage.pop("terminal_at_utc", None)
                self.event(
                    "group_retry_scheduled",
                    stage=name,
                    group_id=group_id,
                    failed_group_count=len(failures),
                    next_group_number=len(failures) + 1,
                    backoff_seconds=STAGE_RETRY_BACKOFF_SEC,
                    job_statuses=stage["job_statuses"],
                )

    def register_group(self, stage_name: str, group_id: str) -> None:
        label = f"{stage_name.replace('_', '-')}-v1-16"
        register = self.run(
            [
                sys.executable,
                str(self.repo / "scripts/ap/watch_t56_oracle_study.py"),
                "--state-dir", str(self.root / "watcher"),
                "--register-group", group_id,
                "--label", label,
            ],
            timeout=60,
        )
        if register.returncode != 0:
            raise RuntimeError(f"failed to register {group_id}: {register.stderr or register.stdout}")
        self.state["stages"][stage_name]["registered_with_evidence_watcher"] = True
        self.save()
        self.event("group_registered", stage=stage_name, group_id=group_id)

    def register_e4_repair(self, job_id: str) -> None:
        register = self.run(
            [
                sys.executable,
                str(self.repo / "scripts/ap/watch_t56_oracle_study.py"),
                "--state-dir", str(self.root / "watcher"),
                "--register-job", job_id,
                "--label", FABLE_E4_LABEL,
            ],
            timeout=60,
        )
        if register.returncode != 0:
            raise RuntimeError(
                f"failed to register E4 repair {job_id}: "
                f"{register.stderr or register.stdout}"
            )
        self.state["fable_e4_repair"]["registered_with_evidence_watcher"] = True
        self.save()
        self.event("e4_repair_registered", job_id=job_id)

    def submit_e4_repair(self) -> None:
        repair = self.state["fable_e4_repair"]
        child = dict(self.environment)
        key = child.get("ROUTIFY_KEY_sig")
        if not key:
            raise RuntimeError("ROUTIFY_KEY_sig is required")
        model = "serve-3.8-maxp-cpt-s1-0715-fable-1ep"
        child.update(
            {
                "MODEL_API_KEY": key,
                "MODEL_BASE_URL": FABLE_ENDPOINTS[0],
                "MODEL_NAME": model,
            }
        )
        command = [
            sys.executable,
            str(self.repo / "scripts/ap/submit.py"),
            "--scope", "environment",
            "--environment-id", "E4",
            "--cluster", self.args.cluster,
            "--agenthub-ref", SELFGEN_AGENTHUB_REF,
            "--dataset", "skillevolbench/skillevolbench",
            "--split", "v1@15",
            "--model", model,
            "--model-base-url", FABLE_ENDPOINTS[0],
            "--harbor-agent", "opencode",
            "--model-provider", "sglang",
            "--model-api-protocol", "openai",
            "--learning-max-attempts", "3",
            "--harbor-agent-timeout-multiplier", "6",
            "--runtime-timeout-sec", "172800",
            "--episode-retry-max-attempts", "2",
            "--episode-retry-backoff-sec", "300",
            "--concurrency", "1",
            "--probe-mode", "chat",
            "--idempotency-key", str(repair["idempotency_key"]),
        ]
        self.heartbeat("submitting_fable_e4_repair")
        dry_run = self.run([*command, "--dry-run"], env=child, timeout=300)
        if dry_run.returncode != 0:
            repair["last_submit_error"] = (dry_run.stdout + "\n" + dry_run.stderr)[-2000:]
            repair["last_submit_attempt_utc"] = utc_now()
            repair["next_submit_attempt_epoch"] = time.time() + 300
            self.event(
                "e4_repair_dry_run_retryable_failure",
                returncode=dry_run.returncode,
            )
            self.save()
            return
        result = self.run(command, env=child, timeout=300)
        combined = result.stdout + "\n" + result.stderr
        job_id = next(
            (
                found
                for value in json_values(combined)
                if (found := find_job_id(value, "E4"))
            ),
            None,
        )
        if result.returncode != 0 or not job_id:
            repair["last_submit_error"] = combined[-2000:]
            repair["last_submit_attempt_utc"] = utc_now()
            repair["next_submit_attempt_epoch"] = time.time() + 300
            self.event(
                "e4_repair_submission_retryable_failure",
                returncode=result.returncode,
            )
            self.save()
            return
        repair.update(
            {
                "status": "submitted",
                "job_id": job_id,
                "submitted_at_utc": utc_now(),
            }
        )
        repair.pop("last_submit_error", None)
        repair.pop("next_submit_attempt_epoch", None)
        self.save()
        self.register_e4_repair(job_id)
        self.event("e4_repair_submitted", job_id=job_id)

    def advance_e4_repair(self) -> tuple[bool, str]:
        repair = self.state["fable_e4_repair"]
        job_id = repair.get("job_id")
        if job_id:
            if repair.get("registered_with_evidence_watcher") is not True:
                self.register_e4_repair(str(job_id))
            job = self.get_job(str(job_id))
            status = str(job.get("status") or "Unknown")
            repair["job_status"] = status
            if status == "Succeeded":
                repair["status"] = "succeeded"
                repair.setdefault("terminal_at_utc", utc_now())
                self.save()
                return True, f"E4 repair terminal: {status}"
            if status in {"Failed", "Cancelled"}:
                failures = repair.setdefault("failed_jobs", [])
                if not isinstance(failures, list):
                    failures = []
                    repair["failed_jobs"] = failures
                known_ids = {
                    str(item.get("job_id"))
                    for item in failures
                    if isinstance(item, dict) and item.get("job_id")
                }
                if str(job_id) not in known_ids:
                    failures.append(
                        {
                            "job_id": str(job_id),
                            "status": status,
                            "observed_at_utc": utc_now(),
                            "idempotency_key": repair.get("idempotency_key"),
                        }
                    )

                if status == "Cancelled" or len(failures) >= MAX_FABLE_E4_REPAIR_JOBS:
                    repair["status"] = "repair_exhausted"
                    repair["repair_exhausted"] = True
                    repair["terminal_at_utc"] = utc_now()
                    self.save()
                    self.event(
                        "e4_repair_exhausted",
                        job_id=job_id,
                        job_status=status,
                        failed_job_count=len(failures),
                    )
                    return True, (
                        "Fable E4 repair needs manual review: "
                        f"{status}, {len(failures)}/{MAX_FABLE_E4_REPAIR_JOBS} jobs"
                    )

                retry_at = time.time() + FABLE_E4_RETRY_BACKOFF_SEC
                repair.update(
                    {
                        "status": "retry_backoff",
                        "job_id": None,
                        "job_status": status,
                        "idempotency_key": str(uuid.uuid4()),
                        "registered_with_evidence_watcher": False,
                        "next_submit_attempt_epoch": retry_at,
                        "last_failed_job_id": str(job_id),
                    }
                )
                repair.pop("submitted_at_utc", None)
                repair.pop("terminal_at_utc", None)
                self.save()
                self.event(
                    "e4_repair_retry_scheduled",
                    job_id=job_id,
                    job_status=status,
                    failed_job_count=len(failures),
                    next_job_number=len(failures) + 1,
                    backoff_seconds=FABLE_E4_RETRY_BACKOFF_SEC,
                )
                return False, (
                    f"Fable E4 repair {job_id} failed; fresh job "
                    f"{len(failures) + 1}/{MAX_FABLE_E4_REPAIR_JOBS} scheduled"
                )
            self.save()
            return False, f"waiting for Fable E4 repair {job_id}: {status}"

        smoke = self.get_job(FABLE_SMOKE_JOB_ID)
        smoke_status = str(smoke.get("status") or "Unknown")
        if smoke_status not in TERMINAL:
            return False, f"waiting for Fable exact-oracle smoke: {smoke_status}"
        if repair.get("repair_exhausted") is True:
            return True, "Fable E4 repair exhausted; manual review required"
        next_attempt = repair.get("next_submit_attempt_epoch", 0)
        if isinstance(next_attempt, (int, float)) and time.time() < next_attempt:
            remaining = int(next_attempt - time.time())
            return False, f"Fable E4 repair preflight backoff: {remaining}s"
        self.submit_e4_repair()
        return False, "submitted Fable E4 repair"

    def prerequisites(self) -> tuple[bool, str]:
        validation = read_json(self.smoke_validation_path, {})
        if not isinstance(validation, dict) or validation.get("valid") is not True:
            return False, "waiting for exported E2 exact-oracle smoke validation"
        inventory = read_json(self.inventory_path, {})
        jobs = inventory.get("jobs", []) if isinstance(inventory, dict) else []
        by_label = {str(job.get("label")): job for job in jobs if isinstance(job, dict)}
        fable_labels = (
            "sig-fable-e3-repair-v1-15",
            "sig-fable-selfgen-v1-13-E5",
        )
        if any(by_label.get(label, {}).get("status") not in TERMINAL for label in fable_labels):
            return False, "waiting for pre-existing Fable jobs to become terminal"
        return True, "ready"

    def qwen_ready(self) -> tuple[bool, str]:
        inventory = read_json(self.inventory_path, {})
        jobs = inventory.get("jobs", []) if isinstance(inventory, dict) else []
        by_label = {str(job.get("label")): job for job in jobs if isinstance(job, dict)}
        e6 = by_label.get("qwen37max-e6-repair-v1-15")
        e1 = by_label.get("qwen37max-e1-repair-v1-15")
        if not e6 or e6.get("status") not in TERMINAL:
            return False, "waiting for Qwen E6 repair"
        if not e1 or e1.get("status") not in TERMINAL:
            return False, "waiting for serialized Qwen E1 repair"
        return True, "ready"

    def submit(self, stage_name: str) -> None:
        stage = self.state["stages"][stage_name]
        model = "qwen3.7-max" if stage_name.startswith("qwen") else "serve-3.8-maxp-cpt-s1-0715-fable-1ep"
        is_oracle = stage_name.endswith("exact_oracle")
        is_curated_all = stage_name.endswith("curated_all")
        suite = f"t56-{stage_name.replace('_', '-')}-v1-16"
        command = [
            sys.executable,
            str(self.repo / "scripts/ap/submit.py"),
            "--scope", "full",
            "--cluster", self.args.cluster,
            "--split", "v1@16",
            "--agenthub-ref", AGENTHUB_REF,
            "--harbor-agent", "opencode",
            "--model", model,
            "--probe-mode", "chat",
            "--evaluation-only-t4-t6",
            "--no-within-env-replay",
            "--no-replay-eval",
            "--runtime-timeout-sec", "172800",
            "--learning-max-attempts", "1",
            "--episode-retry-max-attempts", "2",
            "--episode-retry-backoff-sec", "30",
            "--harbor-agent-timeout-multiplier", "6",
            "--suite-name", suite,
            "--idempotency-key", str(stage["idempotency_key"]),
        ]
        child = dict(self.environment)
        if stage_name.startswith("fable"):
            key = child.get("ROUTIFY_KEY_sig")
            if not key:
                raise RuntimeError("ROUTIFY_KEY_sig is required")
            child.update({
                "MODEL_API_KEY": key,
                "MODEL_BASE_URL": FABLE_ENDPOINTS[0],
                "MODEL_NAME": model,
            })
            command.extend(["--model-provider", "sglang", "--concurrency", "2"])
            for endpoint in FABLE_ENDPOINTS:
                command.extend(["--model-base-url-collection", endpoint])
        else:
            required = {
                "MODEL_API_KEY": child.get("DASHSCOPE_API_KEY"),
                "MODEL_BASE_URL": child.get("DASHSCOPE_API_URL"),
                "MODEL_NAME": child.get("QWEN37_MODEL_NAME") or model,
            }
            if not all(required.values()):
                raise RuntimeError("DASHSCOPE_API_KEY, DASHSCOPE_API_URL, and QWEN37_MODEL_NAME are required")
            child.update({key: str(value) for key, value in required.items()})
            command.extend(["--model-provider", "dashscope", "--concurrency", "1"])
        if is_oracle:
            command.extend(["--baseline-name", "curated_static", "--oracle-skill-view"])
        elif is_curated_all:
            command.extend(["--baseline-name", "curated_static"])
        else:
            command.extend(["--baseline-name", "no_skill"])

        self.heartbeat("submitting_group", stage=stage_name)
        result = self.run(command, env=child, timeout=300)
        combined = result.stdout + "\n" + result.stderr
        group_id = next((found for value in json_values(combined) if (found := find_group_id(value))), None)
        if result.returncode != 0 or not group_id:
            stage["last_submit_error"] = combined[-2000:]
            stage["last_submit_attempt_utc"] = utc_now()
            self.event("submission_retryable_failure", stage=stage_name, returncode=result.returncode)
            self.save()
            return
        stage.update({"status": "submitted", "group_id": group_id, "submitted_at_utc": utc_now()})
        stage.pop("last_submit_error", None)
        stage.pop("next_submit_attempt_epoch", None)
        self.save()
        self.register_group(stage_name, group_id)
        self.event("group_submitted", stage=stage_name, group_id=group_id, suite_name=suite)

    @staticmethod
    def settled(stage: dict[str, Any]) -> bool:
        return stage.get("status") in {"succeeded", "repair_exhausted"}

    @staticmethod
    def ready_to_submit(stage: dict[str, Any]) -> bool:
        if stage.get("status") not in {"pending", "retry_backoff"}:
            return False
        next_attempt = stage.get("next_submit_attempt_epoch", 0)
        return not isinstance(next_attempt, (int, float)) or time.time() >= next_attempt

    def step(self) -> None:
        self.update_submitted_stages()
        stages = self.state["stages"]

        # Qwen and Fable use independent model services.  Conditions remain
        # serialized within each model lane, but a Fable-only smoke/repair gate
        # must not idle Qwen once its own repairs are terminal.
        qwen_ready, qwen_reason = self.qwen_ready()
        if qwen_ready:
            if self.ready_to_submit(stages["qwen_exact_oracle"]):
                self.submit("qwen_exact_oracle")
            elif self.settled(stages["qwen_exact_oracle"]) and self.ready_to_submit(stages["qwen_no_skill"]):
                self.submit("qwen_no_skill")
            elif self.settled(stages["qwen_no_skill"]) and self.ready_to_submit(stages["qwen_curated_all"]):
                self.submit("qwen_curated_all")

        _, e4_reason = self.advance_e4_repair()
        fable_ready, fable_reason = self.prerequisites()
        if fable_ready:
            if self.ready_to_submit(stages["fable_exact_oracle"]):
                self.submit("fable_exact_oracle")
            elif self.settled(stages["fable_exact_oracle"]) and self.ready_to_submit(stages["fable_no_skill"]):
                self.submit("fable_no_skill")
            elif self.settled(stages["fable_no_skill"]) and self.ready_to_submit(stages["fable_curated_all"]):
                self.submit("fable_curated_all")
        self.save()
        all_done = (
            all(stage.get("status") == "succeeded" for stage in stages.values())
            and self.state["fable_e4_repair"].get("status") == "succeeded"
        )
        self.heartbeat(
            "matrix_terminal" if all_done else "monitoring_matrix",
            qwen_gate=qwen_reason,
            fable_gate=fable_reason,
            fable_e4_repair_reason=e4_reason,
        )

    def loop(self) -> int:
        self.event("matrix_watcher_started", pid=os.getpid())
        while True:
            try:
                self.step()
            except (RuntimeError, OSError, subprocess.SubprocessError, json.JSONDecodeError) as exc:
                self.event("transient_error", error=self.redact(str(exc))[-1500:])
                self.heartbeat("transient_error", error=self.redact(str(exc))[-1000:])
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=Path(__file__).resolve().parents[2])
    parser.add_argument("--study-root", type=Path, default=DEFAULT_ROOT)
    parser.add_argument("--cluster", default="hk-benchmark-dev")
    parser.add_argument("--ap-cli", default="ap")
    parser.add_argument("--poll-sec", type=int, default=60)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_sec < 10:
        parser.error("--poll-sec must be at least 10")
    return args


def main() -> int:
    args = parse_args()
    state_dir = args.study_root.resolve() / "matrix-watcher"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (state_dir / "watcher.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        print("another matrix watcher holds the lock", file=sys.stderr)
        return 2
    return MatrixWatcher(args).loop()


if __name__ == "__main__":
    raise SystemExit(main())
