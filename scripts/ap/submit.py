"""Submit SkillEvolBench episodes through the Agent Platform CLI.

The safe default is a one-task E1 infrastructure smoke.  Before invoking
``ap``, the helper probes either the configured OpenAI-compatible endpoint or
the native Anthropic Messages endpoint and verifies the requested model.

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


def _chat_completions_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/chat/completions"
    return f"{normalized}/v1/chat/completions"


def _anthropic_messages_url(base_url: str) -> str:
    normalized = base_url.rstrip("/")
    if normalized.endswith("/v1"):
        return f"{normalized}/messages"
    return f"{normalized}/v1/messages"


class ModelListUnavailableError(RuntimeError):
    """The endpoint does not expose a usable OpenAI ``/models`` surface."""


def probe_model(
    *,
    base_url: str,
    api_key: str,
    model: str,
    timeout: float = 10.0,
    mode: str = "models",
    protocol: str = "openai",
) -> list[str]:
    requested = model.split("/", 1)[-1]
    if protocol not in {"openai", "anthropic"}:
        raise ValueError(f"unsupported model API protocol: {protocol!r}")
    if mode not in {"models", "chat", "auto"}:
        raise ValueError(f"unsupported probe mode: {mode!r}")

    if protocol == "anthropic":
        request = urllib.request.Request(
            _anthropic_messages_url(base_url),
            headers={
                "x-api-key": api_key,
                "anthropic-version": "2023-06-01",
                "Content-Type": "application/json",
            },
            data=json.dumps(
                {
                    "model": requested,
                    "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                    "max_tokens": 16,
                },
                separators=(",", ":"),
            ).encode("utf-8"),
            method="POST",
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
                "Anthropic Messages probe failed for "
                f"{_anthropic_messages_url(base_url)}: {type(exc).__name__}"
            ) from exc
        content = payload.get("content") if isinstance(payload, dict) else None
        returned_model = payload.get("model") if isinstance(payload, dict) else None
        has_text = isinstance(content, list) and any(
            isinstance(block, dict)
            and block.get("type") == "text"
            and isinstance(block.get("text"), str)
            for block in content
        )
        if not has_text:
            raise RuntimeError("Anthropic Messages probe returned no text content")
        if returned_model and returned_model not in {requested, model}:
            raise RuntimeError(
                f"Anthropic Messages probe returned unexpected model {returned_model!r}"
            )
        return [str(returned_model or requested)]

    if mode in {"models", "auto"}:
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
            if mode == "models":
                raise RuntimeError(
                    f"model endpoint probe failed for {_models_url(base_url)}: "
                    f"{type(exc).__name__}"
                ) from exc
            payload = None

        if payload is not None:
            entries = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(entries, list):
                if mode == "models":
                    raise RuntimeError(
                        f"model endpoint probe returned an invalid schema for "
                        f"{_models_url(base_url)}"
                    )
            else:
                model_ids = sorted(
                    str(entry["id"])
                    for entry in entries
                    if isinstance(entry, dict) and entry.get("id")
                )
                if requested not in model_ids and model not in model_ids:
                    raise RuntimeError(
                        f"requested model {model!r} is absent from /v1/models; "
                        f"available ids: {model_ids}"
                    )
                return model_ids

    request = urllib.request.Request(
        _chat_completions_url(base_url),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        data=json.dumps(
            {
                "model": requested,
                "messages": [{"role": "user", "content": "Reply with exactly: OK"}],
                "max_tokens": 16,
            },
            separators=(",", ":"),
        ).encode("utf-8"),
        method="POST",
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
            f"chat completion probe failed for {_chat_completions_url(base_url)}: "
            f"{type(exc).__name__}"
        ) from exc
    choices = payload.get("choices") if isinstance(payload, dict) else None
    returned_model = payload.get("model") if isinstance(payload, dict) else None
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("chat completion probe returned no choices")
    if returned_model and returned_model not in {requested, model}:
        raise RuntimeError(
            f"chat completion probe returned unexpected model {returned_model!r}"
        )
    return [str(returned_model or requested)]


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


def _model_base_urls(args: argparse.Namespace, environ: Mapping[str, str]) -> list[str]:
    """Return the normalized, de-duplicated model endpoint list."""
    raw_urls = list(args.model_base_url_collection or [])
    if args.model_base_url:
        raw_urls.insert(0, args.model_base_url)
    elif not raw_urls and environ.get("MODEL_BASE_URL"):
        raw_urls.append(environ["MODEL_BASE_URL"])

    urls: list[str] = []
    for raw_url in raw_urls:
        normalized = raw_url.strip().rstrip("/")
        if normalized and normalized not in urls:
            urls.append(normalized)
    if not urls:
        raise ValueError("MODEL_BASE_URL is required")
    return urls


@dataclass(frozen=True)
class Submission:
    command: list[str]
    child_env: dict[str, str]
    description: str


def build_submission(
    args: argparse.Namespace, environ: Mapping[str, str]
) -> Submission:
    if args.reference_solution_audit:
        if args.scope not in {"environment", "full"}:
            raise ValueError(
                "--reference-solution-audit requires --scope environment or full"
            )
        if args.evaluation_only_t4_t6 or args.oracle_skill_view:
            raise ValueError(
                "--reference-solution-audit is mutually exclusive with model diagnostics"
            )
    if args.model_api_protocol == "anthropic" and args.harbor_agent != "opencode":
        raise ValueError(
            "--model-api-protocol anthropic currently requires --harbor-agent opencode"
        )
    if args.model_proxy_enabled and args.model_api_protocol != "anthropic":
        raise ValueError(
            "--model-proxy-enabled requires --model-api-protocol anthropic"
        )
    if args.evaluation_only_t4_t6:
        if args.scope not in {"environment", "full"}:
            raise ValueError(
                "--evaluation-only-t4-t6 requires --scope environment or full"
            )
        if args.within_env_replay is True or args.replay_eval is True:
            raise ValueError(
                "--evaluation-only-t4-t6 requires replay disabled"
            )
    if args.oracle_skill_view:
        if not args.evaluation_only_t4_t6:
            raise ValueError(
                "--oracle-skill-view requires --evaluation-only-t4-t6"
            )
        if args.baseline_name != "curated_static":
            raise ValueError(
                "--oracle-skill-view requires --baseline-name curated_static"
            )
    ap_api_key = _required(environ.get("AP_API_KEY"), "AP_API_KEY")
    if args.reference_solution_audit:
        model_api_key = "NOT_REQUIRED"
        model_base_urls = ["http://reference-audit.invalid/v1"]
        model_base_url = model_base_urls[0]
        model = "harbor-oracle"
    else:
        model_api_key = _required(environ.get("MODEL_API_KEY"), "MODEL_API_KEY")
        model_base_urls = _model_base_urls(args, environ)
        model_base_url = model_base_urls[0]
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
    # ``no_skill`` never enters the learning phase, but BaselineConfig still
    # validates the field before the evaluation-only runner can start.  Values
    # above one imply same-session skill updates and are invalid for no_skill.
    effective_learning_max_attempts = (
        1 if args.baseline_name == "no_skill" else args.learning_max_attempts
    )
    params: dict[str, Any] = {
        "dataset": dataset,
        "split": split,
        "model": model,
        "model_base_url": model_base_url,
        "model_api_key": model_api_key,
        "harbor_agent": args.harbor_agent,
        "agent_cli_set": args.harbor_agent,
        "model_provider": args.model_provider,
        "model_api_protocol": args.model_api_protocol,
        "model_probe_mode": args.probe_mode,
        "model_probe_timeout_sec": args.model_probe_timeout_sec,
        "model_proxy_enabled": args.model_proxy_enabled,
        "model_proxy_retry_attempts": args.model_proxy_retry_attempts,
        "model_proxy_request_timeout_sec": args.model_proxy_request_timeout_sec,
        "baseline_name": args.baseline_name,
        "strategy_name": args.strategy_name,
        "order_seed": args.order_seed,
        "learning_max_attempts": effective_learning_max_attempts,
        "harbor_agent_timeout_multiplier": args.harbor_agent_timeout_multiplier,
        "runtime_timeout_sec": args.runtime_timeout_sec,
        "episode_retry_max_attempts": args.episode_retry_max_attempts,
        "episode_retry_backoff_sec": args.episode_retry_backoff_sec,
        "evaluation_only_t4_t6": args.evaluation_only_t4_t6,
        "oracle_skill_view": args.oracle_skill_view,
        "reference_solution_audit": args.reference_solution_audit,
        "reference_audit_concurrency": args.reference_audit_concurrency,
    }
    reasoning_effort = args.reasoning_effort or args.codex_reasoning_effort
    if reasoning_effort:
        params["reasoning_effort"] = reasoning_effort
    # Tri-state CLI flags: omission means "use the selected baseline's yaml".
    # In particular, the same-session baseline intentionally disables replay;
    # an AP launcher must not silently turn it back on.
    if args.within_env_replay is not None:
        params["within_env_replay"] = args.within_env_replay
    if args.replay_eval is not None:
        params["replay_eval"] = args.replay_eval
    if args.harbor_agent == "codex":
        params["codex_wire_api"] = args.codex_wire_api
        params["codex_version"] = args.codex_version
    elif args.harbor_agent == "opencode":
        params["opencode_version"] = _required(
            args.opencode_version, "--opencode-version"
        )
        params["opencode_wire_api"] = args.opencode_wire_api
    if args.agent_runtime_image:
        params["agent_runtime_image"] = args.agent_runtime_image
    if args.model_proxy_image:
        params["model_proxy_image"] = args.model_proxy_image
    if args.model_proxy_envs:
        try:
            proxy_envs = json.loads(args.model_proxy_envs)
        except json.JSONDecodeError as exc:
            raise ValueError("--model-proxy-envs must be valid JSON") from exc
        if not isinstance(proxy_envs, dict):
            raise ValueError("--model-proxy-envs must be a JSON object")
        params["model_proxy_envs"] = json.dumps(
            proxy_envs, ensure_ascii=False, separators=(",", ":")
        )

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
        if len(model_base_urls) > 1 and not args.reference_solution_audit:
            command.extend(
                [
                    "--model-base-url-collection",
                    json.dumps(model_base_urls, separators=(",", ":")),
                ]
            )
        if args.reference_solution_audit:
            description = (
                "non-scoreable six-environment official reference-solution audit "
                f"for dataset {dataset_version}"
            )
        elif not args.evaluation_only_t4_t6:
            command.append("--enable-post-process")
            description = f"full six-environment dataset {dataset_version}"
        else:
            description = (
                "non-scoreable six-environment T4-T6 diagnostic "
                f"for dataset {dataset_version}"
            )
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
        elif args.reference_solution_audit:
            description = (
                f"non-scoreable {environment_id} official reference-solution "
                "audit for T4-T6"
            )
        elif args.evaluation_only_t4_t6:
            description = (
                f"non-scoreable {environment_id} T4-T6 diagnostic "
                f"(oracle_skill_view={args.oracle_skill_view})"
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
        "--model-base-url-collection",
        action="append",
        default=None,
        metavar="URL",
        help=(
            "repeat for each model server; full submissions pass the unique "
            "URL list to AP for server-side load balancing"
        ),
    )
    parser.add_argument(
        "--harbor-agent", choices=("codex", "opencode"), default="opencode"
    )
    parser.add_argument("--model-provider", default="sglang")
    parser.add_argument(
        "--model-api-protocol",
        choices=("openai", "anthropic"),
        default="openai",
        help=(
            "wire protocol used by OpenCode: openai-compatible or native "
            "Anthropic Messages"
        ),
    )
    parser.add_argument(
        "--codex-wire-api", choices=("responses", "chat"), default="responses"
    )
    parser.add_argument(
        "--reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default="",
        help="optional model reasoning effort for Codex or OpenCode",
    )
    parser.add_argument(
        "--codex-reasoning-effort",
        choices=("low", "medium", "high", "xhigh", "max"),
        default="",
        help="deprecated alias for --reasoning-effort",
    )
    parser.add_argument(
        "--codex-version",
        default=os.environ.get("CODEX_VERSION", "0.144.2"),
        help="pinned @openai/codex CLI version used in the task runtime",
    )
    parser.add_argument(
        "--opencode-version",
        default=os.environ.get("OPENCODE_VERSION", "1.18.3"),
    )
    parser.add_argument(
        "--opencode-wire-api",
        choices=("chat", "responses"),
        default="chat",
        help="OpenCode provider path: Chat Completions or OpenAI Responses",
    )
    parser.add_argument("--baseline-name", default="selfgen_in_session_always")
    parser.add_argument("--strategy-name", default="chain")
    parser.add_argument("--order-seed", choices=("A", "B", "C"), default="A")
    parser.add_argument(
        "--evaluation-only-t4-t6",
        action="store_true",
        help=(
            "run only the 15 T4-T6 primary tasks for a matched, non-scoreable "
            "solvability diagnostic"
        ),
    )
    parser.add_argument(
        "--oracle-skill-view",
        action="store_true",
        help=(
            "mount exactly primary_skill for T4/T5 and required_skills for T6; "
            "requires curated_static and --evaluation-only-t4-t6"
        ),
    )
    parser.add_argument(
        "--reference-solution-audit",
        action="store_true",
        help=(
            "run checked-in solution/solve.sh with Harbor's oracle agent "
            "against all 15 T4-T6 tasks; no model endpoint is used"
        ),
    )
    parser.add_argument(
        "--reference-audit-concurrency",
        type=int,
        default=2,
        help="concurrent Harbor oracle trials within each AP job (1-4)",
    )
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
        "--harbor-agent-timeout-multiplier",
        type=float,
        default=6.0,
        help=(
            "Harbor agent timeout multiplier (1-8); AP evaluations default to "
            "6 so a 600-second task receives 60 minutes"
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
    parser.add_argument(
        "--runtime-timeout-sec",
        type=int,
        default=172800,
        help="AP job wall-clock timeout; default 48h leaves room for one fresh retry",
    )
    parser.add_argument(
        "--episode-retry-max-attempts",
        type=int,
        default=2,
        help=(
            "fresh full-episode attempts inside one AP job (1-3); retries only "
            "structured infrastructure failures such as AgentTimeoutError"
        ),
    )
    parser.add_argument(
        "--episode-retry-backoff-sec",
        type=int,
        default=30,
        help="delay before a retryable fresh episode attempt (0-300 seconds)",
    )
    parser.add_argument(
        "--concurrency",
        type=int,
        default=1,
        help=(
            "maximum concurrent environment jobs for a full group (1-6); "
            "the fail-safe default is 1 because API-key and endpoint quotas "
            "must be measured before raising it; pass 6 explicitly for a "
            "validated two-endpoint deployment"
        ),
    )
    parser.add_argument("--queue", default=os.environ.get("AP_QUEUE_ID", ""))
    parser.add_argument("--runner-image", default=os.environ.get("AP_RUNNER_IMAGE", ""))
    parser.add_argument(
        "--agent-runtime-image", default=os.environ.get("AGENT_RUNTIME_IMAGE", "")
    )
    parser.add_argument("--probe-timeout", type=float, default=10.0)
    parser.add_argument(
        "--skip-local-probe",
        action="store_true",
        help=(
            "skip only the submit-host probe; the AP template's host and DinD "
            "probes remain mandatory"
        ),
    )
    parser.add_argument(
        "--model-probe-timeout-sec",
        type=int,
        default=30,
        help="per-request timeout for model probes inside AP main and DinD containers",
    )
    parser.add_argument(
        "--model-proxy-enabled",
        action=argparse.BooleanOptionalAction,
        default=_env_bool("MODEL_PROXY_ENABLED", False),
        help=(
            "route native Anthropic requests through the AP transport proxy; "
            "this buffers and retries one HTTP request without changing verifier "
            "retry semantics"
        ),
    )
    parser.add_argument(
        "--model-proxy-retry-attempts",
        type=int,
        default=int(os.environ.get("MODEL_PROXY_RETRY_ATTEMPTS", "3")),
        help="bounded upstream attempts per Anthropic request (1-10)",
    )
    parser.add_argument(
        "--model-proxy-request-timeout-sec",
        type=int,
        default=int(os.environ.get("MODEL_PROXY_REQUEST_TIMEOUT_SEC", "1800")),
        help="upstream request timeout used by the AP model proxy (30-3600 seconds)",
    )
    parser.add_argument(
        "--model-proxy-image",
        default=os.environ.get("MODEL_PROXY_IMAGE", ""),
        help="optional override for the Agent-Hub model proxy image",
    )
    parser.add_argument(
        "--model-proxy-envs",
        default=os.environ.get("MODEL_PROXY_ENVS", ""),
        help="optional JSON object of additional model proxy environment values",
    )
    parser.add_argument(
        "--probe-mode",
        choices=("models", "chat", "auto"),
        default="models",
        help=(
            "models=require /v1/models; chat=probe Chat Completions directly; "
            "auto=fallback to chat only when /v1/models is unavailable"
        ),
    )
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
    if args.runtime_timeout_sec < 1:
        parser.error("--runtime-timeout-sec must be >= 1")
    if not 1 <= args.learning_max_attempts <= 5:
        parser.error("--learning-max-attempts must be between 1 and 5")
    if not 1.0 <= args.harbor_agent_timeout_multiplier <= 8.0:
        parser.error("--harbor-agent-timeout-multiplier must be between 1 and 8")
    if not 1 <= args.episode_retry_max_attempts <= 3:
        parser.error("--episode-retry-max-attempts must be between 1 and 3")
    if not 0 <= args.episode_retry_backoff_sec <= 300:
        parser.error("--episode-retry-backoff-sec must be between 0 and 300")
    if not 1 <= args.concurrency <= 6:
        parser.error("--concurrency must be between 1 and 6")
    if not 1 <= args.reference_audit_concurrency <= 4:
        parser.error("--reference-audit-concurrency must be between 1 and 4")
    if args.probe_timeout <= 0:
        parser.error("--probe-timeout must be > 0")
    if not 5 <= args.model_probe_timeout_sec <= 300:
        parser.error("--model-probe-timeout-sec must be between 5 and 300")
    if not 1 <= args.model_proxy_retry_attempts <= 10:
        parser.error("--model-proxy-retry-attempts must be between 1 and 10")
    if not 30 <= args.model_proxy_request_timeout_sec <= 3600:
        parser.error("--model-proxy-request-timeout-sec must be between 30 and 3600")

    try:
        submission = build_submission(args, os.environ)
        if args.reference_solution_audit:
            print("Reference-solution audit: model probe is not applicable")
        elif args.skip_local_probe:
            print("Local model probe skipped; AP host and DinD probes remain mandatory")
        else:
            model_api_key = _required(
                os.environ.get("MODEL_API_KEY"), "MODEL_API_KEY"
            )
            model_base_urls = _model_base_urls(args, os.environ)
            model = _required(
                args.model or os.environ.get("MODEL_NAME") or os.environ.get("MODEL"),
                "MODEL_NAME (or MODEL)",
            )
            available_by_url = [
                probe_model(
                    base_url=model_base_url,
                    api_key=model_api_key,
                    model=model,
                    timeout=args.probe_timeout,
                    mode=args.probe_mode,
                    protocol=args.model_api_protocol,
                )
                for model_base_url in model_base_urls
            ]
            print(
                f"Model probe OK: {model.split('/', 1)[-1]} "
                f"({len(model_base_urls)} endpoint(s), "
                f"{sum(map(len, available_by_url))} advertised model id(s))"
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
