#!/usr/bin/env python3
"""Durably submit the frozen v1.1@19 five-lane quality-audit matrix.

The controller deliberately gates the four remaining lanes on a successful,
secret-safe export of E1 from the self-generated group.  With group
concurrency one, E1 is therefore a protocol smoke for the exact immutable
dataset and Agent-Hub revision that the final matrix uses.  Submission is
idempotent and state is version-bound; old v1.1@18 jobs can never be adopted.
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


BENCHMARK_REVISION = "7ecf3fb9d30a551ca31ddcd7856a23e6c18b7b8f"
AGENTHUB_REVISION = "25f8c0becb4d17f8edf3a65767629569e4361827"
DATASET = "skillevolbench/skillevolbench"
DATASET_SPLIT = "v1.1@19"
MODEL = "qwen3.7-max"
LANES = ("self_generated", "no_skill", "exact_curated", "shuffled", "reference")
MODEL_LANES = LANES[:-1]
DEFAULT_ROOT = Path(
    "/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_v1_1_19_20260802"
)


def utc_now() -> str:
    return (
        datetime.now(timezone.utc)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def read_json(path: Path, default: Any) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        return default


def atomic_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    temporary = path.with_name(f".{path.name}.{os.getpid()}.tmp")
    temporary.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.chmod(temporary, 0o600)
    temporary.replace(path)


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


def find_group_id(value: Any) -> str | None:
    if isinstance(value, dict):
        direct = value.get("group_id")
        if isinstance(direct, str) and direct.startswith("group-"):
            return direct
        for child in value.values():
            if found := find_group_id(child):
                return found
    elif isinstance(value, list):
        for child in value:
            if found := find_group_id(child):
                return found
    return None


class MatrixController:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = args.repo_root.resolve()
        self.root = args.audit_root.resolve()
        self.state_dir = self.root / "matrix-controller"
        self.state_path = self.state_dir / "state.json"
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        self.environment.pop("AP_HEADERS", None)
        for variable in ("AP_API_KEY", "MODEL_API_KEY", "MODEL_BASE_URL", "MODEL_NAME"):
            if not self.environment.get(variable):
                raise RuntimeError(f"{variable} is required")
        self.secrets = [
            value
            for name, value in self.environment.items()
            if ("KEY" in name or "SECRET" in name or "TOKEN" in name)
            and len(value) >= 8
        ]
        state = read_json(self.state_path, None)
        if state is None:
            state = {
                "schema_version": 2,
                "created_at_utc": utc_now(),
                "benchmark_revision": BENCHMARK_REVISION,
                "agenthub_revision": AGENTHUB_REVISION,
                "dataset": DATASET,
                "dataset_split": DATASET_SPLIT,
                "model": MODEL,
                "idempotency_keys": {lane: str(uuid.uuid4()) for lane in LANES},
                "group_ids": {lane: None for lane in LANES},
                "smoke_gate": {"status": "not_started"},
            }
            atomic_json(self.state_path, state)
        self._validate_state(state)
        self.state = state

    @staticmethod
    def _validate_state(state: Any) -> None:
        expected = {
            "schema_version": 2,
            "benchmark_revision": BENCHMARK_REVISION,
            "agenthub_revision": AGENTHUB_REVISION,
            "dataset": DATASET,
            "dataset_split": DATASET_SPLIT,
            "model": MODEL,
        }
        if not isinstance(state, dict) or any(state.get(k) != v for k, v in expected.items()):
            raise RuntimeError("matrix controller state belongs to a different protocol version")
        keys = state.get("idempotency_keys")
        groups = state.get("group_ids")
        if not isinstance(keys, dict) or set(keys) != set(LANES):
            raise RuntimeError("matrix controller state has invalid idempotency keys")
        if not isinstance(groups, dict) or set(groups) != set(LANES):
            raise RuntimeError("matrix controller state has invalid group map")
        for value in keys.values():
            try:
                parsed = uuid.UUID(str(value), version=4)
            except ValueError as exc:
                raise RuntimeError("matrix controller state has invalid UUID4") from exc
            if str(parsed) != value:
                raise RuntimeError("matrix controller state has non-canonical UUID4")

    def redact(self, text: str) -> str:
        for secret in self.secrets:
            text = text.replace(secret, "[REDACTED]")
        return text

    def run(
        self, command: list[str], *, timeout: int = 300
    ) -> subprocess.CompletedProcess[str]:
        completed = subprocess.run(
            command,
            cwd=self.repo,
            env=self.environment,
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

    def save(self) -> None:
        self.state["updated_at_utc"] = utc_now()
        atomic_json(self.state_path, self.state)

    def event(self, event: str, **fields: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        with (self.state_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(
                self.redact(
                    json.dumps(
                        {"timestamp_utc": utc_now(), "event": event, **fields},
                        ensure_ascii=False,
                    )
                )
                + "\n"
            )

    def heartbeat(self, phase: str, **fields: Any) -> None:
        atomic_json(
            self.state_dir / "heartbeat.json",
            {
                "updated_at_utc": utc_now(),
                "status": "active",
                "phase": phase,
                "pid": os.getpid(),
                "benchmark_revision": BENCHMARK_REVISION,
                "agenthub_revision": AGENTHUB_REVISION,
                "dataset_split": DATASET_SPLIT,
                "group_ids": self.state["group_ids"],
                "smoke_gate": self.state["smoke_gate"],
                "next_poll_seconds": self.args.poll_sec,
                **fields,
            },
        )

    def template_ready(self) -> tuple[bool, str]:
        result = self.run(
            [
                self.args.ap_cli,
                "template",
                "get",
                "skillevolbench",
                "--agenthub-ref",
                AGENTHUB_REVISION,
            ],
            timeout=120,
        )
        output = result.stdout + "\n" + result.stderr
        ready = (
            result.returncode == 0
            and "shuffled_skill_view" in output
            and "reference_audit_tiers" in output
        )
        return ready, self.redact(output)[-1200:]

    def common_submit(self) -> list[str]:
        return [
            sys.executable,
            str(self.repo / "scripts/ap/submit.py"),
            "--scope",
            "full",
            "--cluster",
            self.args.cluster,
            "--dataset",
            DATASET,
            "--split",
            DATASET_SPLIT,
            "--agenthub-ref",
            AGENTHUB_REVISION,
            "--runtime-timeout-sec",
            "172800",
            "--episode-retry-max-attempts",
            "2",
            "--episode-retry-backoff-sec",
            "30",
            "--concurrency",
            "1",
        ]

    @staticmethod
    def model_flags() -> list[str]:
        return [
            "--harbor-agent",
            "opencode",
            "--model-provider",
            "dashscope",
            "--model-api-protocol",
            "openai",
            "--probe-mode",
            "models",
            "--model-probe-timeout-sec",
            "60",
            "--harbor-agent-timeout-multiplier",
            "6",
        ]

    def command_for(self, lane: str) -> list[str]:
        command = self.common_submit()
        if lane in MODEL_LANES:
            command.extend(self.model_flags())
        if lane == "self_generated":
            command.extend(
                [
                    "--baseline-name",
                    "selfgen_in_session_always",
                    "--learning-max-attempts",
                    "3",
                ]
            )
        elif lane == "no_skill":
            command.extend(
                [
                    "--baseline-name",
                    "no_skill",
                    "--evaluation-only-t4-t6",
                    "--no-within-env-replay",
                    "--no-replay-eval",
                ]
            )
        elif lane in {"exact_curated", "shuffled"}:
            command.extend(
                [
                    "--baseline-name",
                    "curated_static",
                    "--evaluation-only-t4-t6",
                    "--oracle-skill-view" if lane == "exact_curated" else "--shuffled-skill-view",
                    "--learning-max-attempts",
                    "1",
                    "--no-within-env-replay",
                    "--no-replay-eval",
                ]
            )
        elif lane == "reference":
            command.extend(
                [
                    "--reference-solution-audit",
                    "--reference-audit-tiers",
                    "1,2,3,4,5,6",
                    "--reference-audit-concurrency",
                    "2",
                ]
            )
        else:
            raise ValueError(f"unknown lane: {lane}")
        suffix = {
            "self_generated": "self-full180",
            "no_skill": "no-skill-t456",
            "exact_curated": "exact-curated-t456",
            "shuffled": "shuffled-curated-t456",
            "reference": "reference-full180",
        }[lane]
        command.extend(
            [
                "--suite-name",
                f"skillevolbench-v1-1-19-qwen37-{suffix}",
                "--idempotency-key",
                str(self.state["idempotency_keys"][lane]),
            ]
        )
        return command

    def register_group(self, lane: str, group_id: str) -> None:
        result = self.run(
            [
                sys.executable,
                str(self.repo / "scripts/ap/watch_t56_oracle_study.py"),
                "--state-dir",
                str(self.root / "watcher"),
                "--empty-manifest",
                "--register-group",
                group_id,
                "--label",
                f"qwen37-v1-1-19-{lane.replace('_', '-')}",
            ],
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    def submit(self, lane: str) -> bool:
        self.heartbeat("submitting", lane=lane)
        result = self.run(self.command_for(lane), timeout=300)
        combined = result.stdout + "\n" + result.stderr
        group_id = next(
            (
                found
                for value in json_values(combined)
                if (found := find_group_id(value))
            ),
            None,
        )
        if result.returncode != 0 or group_id is None:
            self.state[f"{lane}_last_error"] = combined[-1200:]
            self.save()
            self.event(
                "submission_retryable_failure",
                lane=lane,
                returncode=result.returncode,
            )
            return False
        self.register_group(lane, group_id)
        self.state["group_ids"][lane] = group_id
        self.state.pop(f"{lane}_last_error", None)
        self.save()
        self.event("group_submitted", lane=lane, group_id=group_id)
        return True

    def _self_e1_row(self) -> dict[str, Any] | None:
        group_id = self.state["group_ids"]["self_generated"]
        inventory = read_json(self.root / "watcher" / "inventory.json", {})
        rows = [
            row
            for row in inventory.get("jobs", [])
            if isinstance(row, dict)
            and row.get("group_id") == group_id
            and row.get("instance_id") == "E1"
        ]
        return rows[0] if len(rows) == 1 else None

    def validate_smoke_export(self, row: dict[str, Any]) -> tuple[bool, str]:
        marker = read_json(
            self.root / "watcher" / "exports" / f"{row['job_id']}.json", {}
        )
        if marker.get("completed") is not True:
            return False, "waiting for E1 export"
        if marker.get("unsafe") is True or marker.get("scan_summary", {}).get("clean") is not True:
            return False, "E1 export was quarantined by the safety scan"
        destination = Path(str(marker.get("destination", "")))
        output = destination / "artifacts" / "output"
        job = read_json(destination / "job.json", {})
        manifest = read_json(output / "ap_run_manifest.json", {})
        metrics = read_json(output / "metrics.json", {})
        pruning = read_json(output / "runtime_artifact_pruning_manifest.json", {})
        reports = list((output / "runs").glob("*/reports/full_report.json"))
        checks = {
            "template_commit": job.get("template_commit") == AGENTHUB_REVISION,
            "benchmark_revision": manifest.get("benchmark_revision") == BENCHMARK_REVISION,
            "environment": manifest.get("environment_id") == "E1",
            "canonical": manifest.get("canonical") is True,
            "baseline": manifest.get("baseline_name") == "selfgen_in_session_always",
            "attempt_budget": manifest.get("learning_max_attempts") == 3,
            "all_tiers": manifest.get("evaluation_only_t4_t6") is False,
            "no_replay": (
                manifest.get("within_env_replay") is False
                and manifest.get("replay_eval") is False
            ),
            "pruning_count": pruning.get("removed_directory_count") == 30,
            "pruning_bound": (
                manifest.get("runtime_artifact_pruning")
                == metrics.get("runtime_artifact_pruning")
                == {
                    key: pruning.get(key)
                    for key in (
                        "schema_version",
                        "policy",
                        "manifest",
                        "removed_directory_count",
                        "removed_regular_file_count",
                        "removed_regular_file_bytes",
                        "removed_symlink_count",
                    )
                }
            ),
            "canonical_exports": (
                len(pruning.get("removed_directories", [])) == 30
                and all(
                    isinstance(record, dict)
                    for record in pruning.get("removed_directories", [])
                )
                and all(
                    record.get("canonical_trajectory_sha256")
                    and record.get("canonical_session_export_sha256")
                    for record in pruning.get("removed_directories", [])
                )
            ),
            "full_report": len(reports) == 1,
            "task_count": (
                len(reports) == 1
                and read_json(reports[0], {}).get("n_tasks_attempted") == 30
            ),
            "no_workspace_policy_violation": (
                metrics.get("n_task_workspace_violations") == 0
                and metrics.get("n_reflection_task_workspace_violations") == 0
            ),
        }
        failed = sorted(key for key, passed in checks.items() if not passed)
        atomic_json(
            self.state_dir / "self_e1_smoke_validation.json",
            {
                "validated_at_utc": utc_now(),
                "job_id": row["job_id"],
                "group_id": row["group_id"],
                "checks": checks,
                "passed": not failed,
                "failed_checks": failed,
            },
        )
        return (not failed), ("ok" if not failed else f"failed checks: {', '.join(failed)}")

    def smoke_step(self) -> tuple[bool, str]:
        row = self._self_e1_row()
        if row is None:
            return False, "waiting for self-generated E1 inventory"
        status = row.get("status")
        if status in {"Failed", "Cancelled"}:
            detail = {
                "failed_at_utc": utc_now(),
                "job_id": row.get("job_id"),
                "group_id": row.get("group_id"),
                "status": status,
                "error_code": row.get("error_code"),
            }
            atomic_json(self.state_dir / "self_e1_smoke_failure.json", detail)
            self.state["smoke_gate"] = {"status": "failed", **detail}
            self.save()
            return False, "self-generated E1 smoke failed; remaining lanes are held"
        if status != "Succeeded":
            return False, f"self-generated E1 smoke is {status or 'not visible'}"
        passed, reason = self.validate_smoke_export(row)
        if passed:
            self.state["smoke_gate"] = {
                "status": "passed",
                "passed_at_utc": utc_now(),
                "job_id": row["job_id"],
                "group_id": row["group_id"],
            }
            self.save()
            self.event("self_e1_smoke_passed", job_id=row["job_id"])
        return passed, reason

    def step(self) -> bool:
        if all(self.state["group_ids"].values()):
            atomic_json(
                self.state_dir / "completed.json",
                {
                    "completed_at_utc": utc_now(),
                    "claim": "five_lanes_submitted_after_exact_revision_smoke",
                    "benchmark_revision": BENCHMARK_REVISION,
                    "agenthub_revision": AGENTHUB_REVISION,
                    "dataset_split": DATASET_SPLIT,
                    "group_ids": self.state["group_ids"],
                    "smoke_gate": self.state["smoke_gate"],
                },
            )
            self.heartbeat("completed")
            return True

        ready, diagnostic = self.template_ready()
        if not ready:
            self.heartbeat("waiting_for_agenthub_publish", diagnostic=diagnostic)
            return False

        if not self.state["group_ids"]["self_generated"]:
            self.submit("self_generated")
            return False

        if self.state["smoke_gate"].get("status") != "passed":
            passed, reason = self.smoke_step()
            self.heartbeat("smoke_gate_passed" if passed else "waiting_for_smoke_gate", reason=reason)
            if not passed:
                return False

        for lane in LANES[1:]:
            if not self.state["group_ids"][lane]:
                self.submit(lane)
                return False
        return False

    def run_forever(self) -> int:
        self.event("controller_started", pid=os.getpid())
        while True:
            try:
                if self.step():
                    return 0
            except (OSError, RuntimeError, subprocess.SubprocessError, ValueError) as exc:
                diagnostic = self.redact(str(exc))[-1200:]
                self.event("transient_error", diagnostic=diagnostic)
                self.heartbeat("transient_error", diagnostic=diagnostic)
            if self.args.once:
                return 0
            time.sleep(self.args.poll_sec)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root", type=Path, default=Path(__file__).resolve().parents[2]
    )
    parser.add_argument("--audit-root", type=Path, default=DEFAULT_ROOT)
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
    state_dir = args.audit_root.resolve() / "matrix-controller"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_handle = (state_dir / "controller.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 75
    return MatrixController(args).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
