#!/usr/bin/env python3
"""Submit the two missing full-audit controls once Agent-Hub is published.

The watcher pins the exact Agent-Hub commit that introduces
``shuffled_skill_view`` and all-tier reference audits. It records only redacted
diagnostics and AP identifiers; credentials remain in the process environment.
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


AGENTHUB_REVISION = "c0fb2b2a34bdab8fddea9082dd38b85db466f4df"
DATASET_SPLIT = "v1.1@18"
DEFAULT_ROOT = Path("/cpfs02/user/zhangfengji.zfj/skillevolbench_180_audit_20260802")


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


class Watcher:
    def __init__(self, args: argparse.Namespace) -> None:
        self.args = args
        self.repo = args.repo_root.resolve()
        self.root = args.audit_root.resolve()
        self.state_dir = self.root / "missing-control-watcher"
        self.state_path = self.state_dir / "state.json"
        self.environment = os.environ.copy()
        self.environment["AP_CLUSTER"] = args.cluster
        # An explicit cluster must win over any stale legacy routing header
        # inherited from a long-lived shell or private env file.
        self.environment.pop("AP_HEADERS", None)
        if not self.environment.get("AP_API_KEY"):
            raise RuntimeError("AP_API_KEY is required")
        self.secrets = [
            value
            for name, value in self.environment.items()
            if ("KEY" in name or "SECRET" in name or "TOKEN" in name)
            and len(value) >= 8
        ]
        state = read_json(self.state_path, {})
        if not isinstance(state, dict) or state.get("schema_version") != 1:
            state = {
                "schema_version": 1,
                "created_at_utc": utc_now(),
                "agenthub_revision": AGENTHUB_REVISION,
                "shuffled_idempotency_key": str(uuid.uuid4()),
                "reference_idempotency_key": str(uuid.uuid4()),
                "shuffled_group_id": None,
                "reference_group_id": None,
            }
            atomic_json(self.state_path, state)
        self.state = state

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

    def heartbeat(self, phase: str, **fields: Any) -> None:
        atomic_json(
            self.state_dir / "heartbeat.json",
            {
                "updated_at_utc": utc_now(),
                "status": "active",
                "phase": phase,
                "pid": os.getpid(),
                "agenthub_revision": AGENTHUB_REVISION,
                "shuffled_group_id": self.state.get("shuffled_group_id"),
                "reference_group_id": self.state.get("reference_group_id"),
                "next_poll_seconds": self.args.poll_sec,
                **fields,
            },
        )

    def event(self, event: str, **fields: Any) -> None:
        self.state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
        line = self.redact(
            json.dumps(
                {"timestamp_utc": utc_now(), "event": event, **fields},
                ensure_ascii=False,
            )
        )
        with (self.state_dir / "events.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(line + "\n")

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
        return ready, self.redact(output)[-1000:]

    def common_submit(self) -> list[str]:
        return [
            sys.executable,
            str(self.repo / "scripts/ap/submit.py"),
            "--scope",
            "full",
            "--cluster",
            self.args.cluster,
            "--dataset",
            "skillevolbench/skillevolbench",
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
            "2",
        ]

    def command_for(self, condition: str) -> list[str]:
        command = self.common_submit()
        if condition == "shuffled":
            command.extend(
                [
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
                    "--baseline-name",
                    "curated_static",
                    "--evaluation-only-t4-t6",
                    "--shuffled-skill-view",
                    "--learning-max-attempts",
                    "1",
                    "--no-within-env-replay",
                    "--no-replay-eval",
                    "--harbor-agent-timeout-multiplier",
                    "6",
                    "--suite-name",
                    "skillevolbench-v1-1-18-qwen37-shuffled-t456",
                    "--idempotency-key",
                    str(self.state["shuffled_idempotency_key"]),
                ]
            )
        elif condition == "reference":
            command.extend(
                [
                    "--reference-solution-audit",
                    "--reference-audit-tiers",
                    "1,2,3,4,5,6",
                    "--reference-audit-concurrency",
                    "2",
                    "--suite-name",
                    "skillevolbench-v1-1-18-reference-full180",
                    "--idempotency-key",
                    str(self.state["reference_idempotency_key"]),
                ]
            )
        else:
            raise ValueError(f"unknown condition: {condition}")
        return command

    def register_group(self, condition: str, group_id: str) -> None:
        label = {
            "shuffled": "qwen37-v1-1-18-shuffled-curated",
            "reference": "v1-1-18-reference-all-tiers",
        }[condition]
        result = self.run(
            [
                sys.executable,
                str(self.repo / "scripts/ap/watch_t56_oracle_study.py"),
                "--state-dir",
                str(self.root / "watcher"),
                "--register-group",
                group_id,
                "--label",
                label,
            ],
            timeout=60,
        )
        if result.returncode != 0:
            raise RuntimeError(result.stderr.strip() or result.stdout.strip())

    def submit(self, condition: str) -> bool:
        self.heartbeat("submitting", condition=condition)
        result = self.run(self.command_for(condition), timeout=300)
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
            self.state[f"{condition}_last_error"] = combined[-1000:]
            self.save()
            self.event(
                "submission_retryable_failure",
                condition=condition,
                returncode=result.returncode,
            )
            return False
        self.register_group(condition, group_id)
        self.state[f"{condition}_group_id"] = group_id
        self.state.pop(f"{condition}_last_error", None)
        self.save()
        self.event("group_submitted", condition=condition, group_id=group_id)
        return True

    def step(self) -> bool:
        if self.state.get("shuffled_group_id") and self.state.get("reference_group_id"):
            atomic_json(
                self.state_dir / "completed.json",
                {
                    "completed_at_utc": utc_now(),
                    "shuffled_group_id": self.state["shuffled_group_id"],
                    "reference_group_id": self.state["reference_group_id"],
                    "agenthub_revision": AGENTHUB_REVISION,
                },
            )
            self.heartbeat("completed")
            return True

        ready, diagnostic = self.template_ready()
        if not ready:
            self.heartbeat(
                "waiting_for_agenthub_publish",
                diagnostic=diagnostic,
            )
            return False

        self.event("agenthub_template_ready", revision=AGENTHUB_REVISION)
        if not self.state.get("shuffled_group_id"):
            self.submit("shuffled")
            return False
        if not self.state.get("reference_group_id"):
            self.submit("reference")
            return False
        return False

    def run_forever(self) -> int:
        self.event("watcher_started", pid=os.getpid())
        while True:
            try:
                if self.step():
                    return 0
            except (OSError, RuntimeError, subprocess.SubprocessError) as exc:
                diagnostic = self.redact(str(exc))[-1000:]
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
    parser.add_argument("--poll-sec", type=int, default=120)
    parser.add_argument("--once", action="store_true")
    args = parser.parse_args()
    if args.poll_sec < 10:
        parser.error("--poll-sec must be at least 10")
    return args


def main() -> int:
    args = parse_args()
    state_dir = args.audit_root.resolve() / "missing-control-watcher"
    state_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock_handle = (state_dir / "watcher.lock").open("a+", encoding="utf-8")
    try:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        return 75
    return Watcher(args).run_forever()


if __name__ == "__main__":
    raise SystemExit(main())
