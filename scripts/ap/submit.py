"""Submit SkillEvolBench episodes through the Agent Platform CLI.

The safe default is a one-task E1 infrastructure smoke.  Before invoking
``ap``, the helper probes the configured OpenAI-compatible ``/v1/models``
endpoint and verifies that the requested served model is present.

Credentials are accepted only through environment variables and are never
written to disk or printed:

* ``AP_API_KEY``
* ``MODEL_API_KEY``
* ``MODEL_BASE_URL``
* ``MODEL_NAME`` (``MODEL`` is accepted as a compatibility fallback)
* ``AP_AGENTHUB_REF`` (or ``--agenthub-ref``)
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

DEFAULT_AP_BASE_URL = "http://agentplatform.aliyun-inc.com"
DEFAULT_CLUSTER = "benchmark-dev"
DEFAULT_DATASET = "skillevolbench/skillevolbench"
DEFAULT_SPLIT = "v1@0"


def _required(value: str | None, description: str) -> str:
    normalized = (value or "").strip()
    if not normalized:
        raise ValueError(f"{description} is required")
    return normalized


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _models_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/models"
    return f"{normalized}/v1/models"


def probe_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float = 10.0,
) -> list[str]:
    request = urllib.request.Request(
        _models_url(base_url),
        headers={"Authorization": f"Bearer {api_key}"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except (
        urllib.error.URLError,
        TimeoutError,
        UnicodeDecodeError,
        json.JSONDecodeError,
    ) as exc:
        raise RuntimeError(
            f"model endpoint probe failed for {_models_url(base_url)}: "
            f"{type(exc).__name__}"
        ) from exc

    entries = payload.get("data", []) if isinstance(payload, dict) else []
    model_ids = sorted(
        str(entry["id"])
        for entry in entries
        if isinstance(entry, dict) and entry.get("id")
    )
    requested = model.split("/", 1)[-1]
    if requested not in model_ids and model not in model_ids:
        raise RuntimeError(
            f"requested model {model!r} is absent from /v1/models; "
            f"available ids: {model_ids}"
        )
    return model_ids


def _sanitize(text: str, secrets: list[str]) -> str:
    sanitized = text
    for secret in secrets:
        if secret:
            sanitized = sanitized.replace(secret, "[REDACTED]")
    sanitized = re.sub(r"\b(?:sk|ap)-[A-Za-z0-9_-]{6,}\b", "[REDACTED]", sanitized)
    sanitized = re.sub(
        r'(?i)("?(?:model_api_key|api_key|authorization)"?\s*[:=]\s*")[^"]*(")',
        r"\1[REDACTED]\2",
        sanitized,
    )
    return sanitized


@dataclass(frozen=True)
class Submission:
    command: list[str]
    child_env: dict[str, str]
    description: str


def build_submission(
    args: argparse.Namespace, environ: Mapping[str, str]
) -> Submission:
    ap_api_key = _required(environ.get("AP_API_KEY"), "AP_API_KEY")
    model_api_key = _required(environ.get("MODEL_API_KEY"), "MODEL_API_KEY")
    model_base_url = _required(
        args.model_base_url or environ.get("MODEL_BASE_URL"), "MODEL_BASE_URL"
    ).rstrip("/")
    model = _required(
        args.model or environ.get("MODEL_NAME") or environ.get("MODEL"),
        "MODEL_NAME (or MODEL)",
    )
    agenthub_ref = _required(
        args.agenthub_ref or environ.get("AP_AGENTHUB_REF"),
        "AP_AGENTHUB_REF (or --agenthub-ref)",
    )

    dataset = args.dataset.rstrip("/")
    split = args.split.strip("/")
    dataset_version = f"{dataset}/{split}"
    params: dict[str, Any] = {
        "dataset": dataset,
        "split": split,
        "model": model,
        "model_base_url": model_base_url,
        "model_api_key": model_api_key,
        "harbor_agent": args.harbor_agent,
        "model_provider": args.model_provider,
        "codex_wire_api": args.codex_wire_api,
        "baseline_name": args.baseline_name,
        "strategy_name": args.strategy_name,
        "order_seed": args.order_seed,
        "within_env_replay": args.within_env_replay,
        "replay_eval": args.replay_eval,
        "runtime_timeout_sec": args.runtime_timeout_sec,
    }
    if args.agent_runtime_image:
        params["agent_runtime_image"] = args.agent_runtime_image

    if args.scope == "smoke":
        params["smoke_max_tasks"] = args.smoke_max_tasks

    command = [
        args.ap_cli,
        "--cluster",
        args.cluster,
        "job",
        "create",
        args.template,
        "--agenthub-ref",
        agenthub_ref,
        "-p",
        json.dumps(params, ensure_ascii=False, separators=(",", ":")),
    ]

    if args.scope == "full":
        # AP accepts suite_name only for a batch/group submission.  A smoke or
        # one-environment episode is a single job and must omit it.
        command.extend(["--suite-name", args.suite_name])
        command.extend(
            ["--dataset", dataset_version, "--concurrency", str(args.concurrency)]
        )
        command.append("--enable-post-process")
        description = f"full six-environment dataset {dataset_version}"
    else:
        environment_id = args.environment_id
        command.extend(["--instance-id", environment_id, "--concurrency", "1"])
        if args.scope == "smoke":
            description = (
                f"non-scoreable {environment_id} smoke "
                f"({args.smoke_max_tasks} task(s))"
            )
        else:
            description = f"complete {environment_id} environment episode"

    command.extend(["--format", "json"])

    if args.queue:
        command.extend(["--queue", args.queue])
    if args.runner_image:
        command.extend(
            [
                "--overrides",
                json.dumps({"image": args.runner_image}, separators=(",", ":")),
            ]
        )
    if args.dry_run:
        command.append("--dry-run")

    child_env = dict(environ)
    child_env.update(
        {
            "AP_API_KEY": ap_api_key,
            "AP_BASE_URL": args.ap_base_url,
            "AP_CLUSTER": args.cluster,
            "AP_AGENTHUB_REF": agenthub_ref,
        }
    )
    # Avoid an inherited legacy header disagreeing with explicit --cluster.
    child_env.pop("AP_HEADERS", None)
    return Submission(command=command, child_env=child_env, description=description)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--scope",
        choices=("smoke", "environment", "full"),
        default="smoke",
        help="smoke=truncated E1 by default; environment=one full episode; full=E1-E6",
    )
    parser.add_argument(
        "--environment-id",
        choices=tuple(f"E{i}" for i in range(1, 7)),
        default="E1",
    )
    parser.add_argument("--smoke-max-tasks", type=int, default=1)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--cluster", default=os.environ.get("AP_CLUSTER", DEFAULT_CLUSTER)
    )
    parser.add_argument(
        "--ap-base-url",
        default=os.environ.get("AP_BASE_URL", DEFAULT_AP_BASE_URL),
    )
    parser.add_argument("--ap-cli", default="ap")
    parser.add_argument("--agenthub-ref", default=None)
    parser.add_argument("--template", default="skillevolbench")
    parser.add_argument("--dataset", default=DEFAULT_DATASET)
    parser.add_argument("--split", default=DEFAULT_SPLIT)
    parser.add_argument("--model", default=None)
    parser.add_argument("--model-base-url", default=None)
    parser.add_argument("--harbor-agent", default="codex")
    parser.add_argument("--model-provider", default="sglang")
    parser.add_argument(
        "--codex-wire-api", choices=("responses", "chat"), default="responses"
    )
    parser.add_argument("--baseline-name", default="selfgen_experience_always")
    parser.add_argument("--strategy-name", default="chain")
    parser.add_argument("--order-seed", choices=("A", "B", "C"), default="A")
    parser.add_argument(
        "--within-env-replay",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("WITHIN_ENV_REPLAY", True),
    )
    parser.add_argument(
        "--replay-eval",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("REPLAY_EVAL", False),
    )
    parser.add_argument("--runtime-timeout-sec", type=int, default=86400)
    parser.add_argument("--concurrency", type=int, default=6)
    parser.add_argument("--queue", default=os.environ.get("AP_QUEUE_ID", ""))
    parser.add_argument("--runner-image", default=os.environ.get("AP_RUNNER_IMAGE", ""))
    parser.add_argument(
        "--agent-runtime-image", default=os.environ.get("AGENT_RUNTIME_IMAGE", "")
    )
    parser.add_argument("--probe-timeout", type=float, default=10.0)
    parser.add_argument(
        "--suite-name",
        default=f"skillevolbench-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if args.smoke_max_tasks < 1:
        parser.error("--smoke-max-tasks must be >= 1")
    if args.smoke_max_tasks > 30:
        parser.error("--smoke-max-tasks must be <= 30")
    if args.concurrency < 1:
        parser.error("--concurrency must be >= 1")
    if args.runtime_timeout_sec < 1:
        parser.error("--runtime-timeout-sec must be >= 1")
    if args.probe_timeout <= 0:
        parser.error("--probe-timeout must be > 0")

    try:
        submission = build_submission(args, os.environ)
        model_api_key = _required(os.environ.get("MODEL_API_KEY"), "MODEL_API_KEY")
        model_base_url = _required(
            args.model_base_url or os.environ.get("MODEL_BASE_URL"), "MODEL_BASE_URL"
        )
        model = _required(
            args.model or os.environ.get("MODEL_NAME") or os.environ.get("MODEL"),
            "MODEL_NAME (or MODEL)",
        )
        available = probe_model(
            base_url=model_base_url,
            api_key=model_api_key,
            model=model,
            timeout=args.probe_timeout,
        )
        print(
            f"Model probe OK: {model.split('/', 1)[-1]} "
            f"({len(available)} model id(s))"
        )
        mode = "AP dry-run" if args.dry_run else "AP submission"
        print(f"Starting {mode}: {submission.description}")
        completed = subprocess.run(
            submission.command,
            env=submission.child_env,
            text=True,
            capture_output=True,
            check=False,
        )
        secrets = [
            os.environ.get("AP_API_KEY", ""),
            os.environ.get("MODEL_API_KEY", ""),
        ]
        if completed.stdout:
            print(_sanitize(completed.stdout, secrets), end="")
        if completed.stderr:
            print(_sanitize(completed.stderr, secrets), end="", file=sys.stderr)
        return completed.returncode
    except (ValueError, RuntimeError, OSError) as exc:
        print(
            _sanitize(
                f"ERROR: {exc}\n",
                [
                    os.environ.get("AP_API_KEY", ""),
                    os.environ.get("MODEL_API_KEY", ""),
                ],
            ),
            end="",
            file=sys.stderr,
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
