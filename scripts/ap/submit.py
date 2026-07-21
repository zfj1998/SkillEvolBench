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
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Mapping

DEFAULT_AP_BASE_URL = "http://agentplatform.aliyun-inc.com"
DEFAULT_CLUSTER = "benchmark-dev"
DEFAULT_DATASET = "skillevolbench/skillevolbench"
DEFAULT_SPLIT = "v1@7"


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


def _env_optional_bool(name: str) -> bool | None:
    """Read an optional boolean without overriding benchmark config defaults."""
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    return _env_bool(name, False)


def _uuid4(raw: str) -> str:
    """Normalize an explicit AP idempotency key and require UUID4."""
    try:
        value = uuid.UUID(raw)
    except ValueError as exc:
        raise argparse.ArgumentTypeError("must be a valid UUID4") from exc
    if value.version != 4:
        raise argparse.ArgumentTypeError("must be a UUID4")
    return str(value)


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
        "agent_cli_set": args.harbor_agent,
        "model_provider": args.model_provider,
        "baseline_name": args.baseline_name,
        "strategy_name": args.strategy_name,
        "order_seed": args.order_seed,
        "learning_max_attempts": args.learning_max_attempts,
        "runtime_timeout_sec": args.runtime_timeout_sec,
    }
    # Tri-state CLI flags: omission means "use the selected baseline's yaml".
    # In particular, the same-session baseline intentionally disables replay;
    # an AP launcher must not silently turn it back on.
    if args.within_env_replay is not None:
        params["within_env_replay"] = args.within_env_replay
    if args.replay_eval is not None:
        params["replay_eval"] = args.replay_eval
    if args.harbor_agent == "codex":
        params["codex_wire_api"] = args.codex_wire_api
    elif args.harbor_agent == "opencode":
        params["opencode_version"] = _required(
            args.opencode_version, "--opencode-version"
        )
    if args.agent_runtime_image:
        params["agent_runtime_image"] = args.agent_runtime_image

    if args.scope == "smoke":
        params["smoke_max_tasks"] = args.smoke_max_tasks
    elif args.scope == "family":
        if args.within_env_replay is True or args.replay_eval is True:
            raise ValueError(
                "--scope family requires replay disabled; omit the replay "
                "flags or pass --no-within-env-replay --no-replay-eval"
            )
        params["smoke_family_id"] = args.family_id

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
        environment_id = (
            args.family_id.split("-", 1)[0]
            if args.scope == "family"
            else args.environment_id
        )
        command.extend(["--instance-id", environment_id, "--concurrency", "1"])
        if args.scope == "smoke":
            description = (
                f"non-scoreable {environment_id} smoke ({args.smoke_max_tasks} task(s))"
            )
        elif args.scope == "family":
            description = (
                f"non-scoreable {args.family_id} T1-T6 family smoke "
                f"in one stateful session sequence"
            )
        else:
            description = f"complete {environment_id} environment episode"

    command.extend(["--format", "json"])

    if args.idempotency_key:
        command.extend(["--idempotency-key", args.idempotency_key])

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
        choices=("smoke", "family", "environment", "full"),
        default="smoke",
        help=(
            "smoke=truncated E1; family=one non-canonical T1-T6 family; "
            "environment=one complete episode; full=E1-E6"
        ),
    )
    parser.add_argument(
        "--environment-id",
        choices=tuple(f"E{i}" for i in range(1, 7)),
        default="E1",
    )
    parser.add_argument("--smoke-max-tasks", type=int, default=1)
    parser.add_argument(
        "--family-id",
        choices=tuple(
            f"E{env}-LS{family}" for env in range(1, 7) for family in range(1, 6)
        ),
        default="E1-LS1",
        help="single family selected by --scope family (default: E1-LS1)",
    )
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
    parser.add_argument(
        "--harbor-agent", choices=("codex", "opencode"), default="opencode"
    )
    parser.add_argument("--model-provider", default="sglang")
    parser.add_argument(
        "--codex-wire-api", choices=("responses", "chat"), default="responses"
    )
    parser.add_argument(
        "--opencode-version",
        default=os.environ.get("OPENCODE_VERSION", "1.18.3"),
    )
    parser.add_argument("--baseline-name", default="selfgen_in_session_always")
    parser.add_argument("--strategy-name", default="chain")
    parser.add_argument("--order-seed", choices=("A", "B", "C"), default="A")
    parser.add_argument(
        "--learning-max-attempts",
        type=int,
        default=3,
        help=(
            "maximum same-session verifier-backed attempts for each T1-T3 "
            "task (1-5; T4-T6 remain one-shot)"
        ),
    )
    parser.add_argument(
        "--within-env-replay",
        action=argparse.BooleanOptionalAction,
        default=_env_optional_bool("WITHIN_ENV_REPLAY"),
    )
    parser.add_argument(
        "--replay-eval",
        action=argparse.BooleanOptionalAction,
        default=_env_optional_bool("REPLAY_EVAL"),
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
    parser.add_argument(
        "--idempotency-key",
        type=_uuid4,
        default=None,
        help=(
            "Stable UUID4 for retrying one logical AP submission without "
            "duplicating jobs. Reuse the same value after an ambiguous "
            "transport failure."
        ),
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
    if not 1 <= args.learning_max_attempts <= 5:
        parser.error("--learning-max-attempts must be between 1 and 5")
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
            f"Model probe OK: {model.split('/', 1)[-1]} ({len(available)} model id(s))"
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
