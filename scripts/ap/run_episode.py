"""Run one SkillEvolBench environment episode under Agent Platform.

AP injects template parameters as environment variables. This entrypoint turns
those values into a validated RunConfig, keeps stateful Harbor data under the
optional DinD-shared ``SEVB_WORKSPACE_ROOT``, and always writes the AP
``OUTPUT_DIR/metrics.json`` contract. It never persists model or platform
credentials in the run manifest.
"""

from __future__ import annotations

import asyncio
import json
import os
import secrets
import subprocess
import sys
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.baselines import load_baseline  # noqa: E402
from skillevolbench.components import UnscoreableTrialError  # noqa: E402
from skillevolbench.orchestration import LifelongRunner  # noqa: E402
from skillevolbench.schemas import (  # noqa: E402
    BaselineConfig,
    RunConfig,
    StrategyConfig,
)


_NO_AUTH_PLACEHOLDERS = frozenset(
    {"DUMMY", "EMPTY", "NONE", "NOT-REQUIRED", "NOT_REQUIRED", "NULL"}
)


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    normalized = raw.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"{name} must be a boolean, got {raw!r}")


def _env_int(name: str, default: int, *, minimum: int, maximum: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be an integer, got {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def _env_float(name: str, default: float, *, minimum: float, maximum: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw.strip() == "":
        return default
    try:
        value = float(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a number, got {raw!r}") from exc
    if not minimum <= value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}, got {value}")
    return value


def _required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise ValueError(f"Required environment variable {name} is empty")
    return value


def _runtime_model_api_key(value: str) -> str:
    """Replace no-auth sentinels with a collision-resistant runtime value.

    Harbor scrubs resolved sensitive environment values from every text file in
    a trial directory. A generic sentinel such as ``EMPTY`` can therefore
    corrupt ordinary source identifiers and trajectory text. The local SGLang
    endpoint does not authenticate, but the client still requires a non-empty
    key, so use an ephemeral high-entropy value that Harbor can safely scrub.
    """

    if value.strip().upper() in _NO_AUTH_PLACEHOLDERS:
        return f"sevb-no-auth-{secrets.token_hex(24)}"
    return value


def _safe_git_revision() -> str:
    revision_file = REPO_ROOT / ".skillevolbench-revision"
    if revision_file.is_file():
        revision = revision_file.read_text().strip()
        if revision:
            return revision
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=REPO_ROOT,
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except Exception:
        return "unknown"


def _sanitize_error(message: str) -> str:
    sanitized = message
    for env_name in (
        "MODEL_API_KEY",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "AP_API_KEY",
        "OSS_ACCESS_KEY_ID",
        "OSS_ACCESS_KEY_SECRET",
    ):
        value = os.environ.get(env_name, "")
        if value:
            sanitized = sanitized.replace(value, "[REDACTED]")
    return sanitized[:2000]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _actionable_exception(exc: BaseException) -> BaseException:
    """Select the useful leaf from a Python 3.11 TaskGroup ExceptionGroup."""
    leaves: list[BaseException] = []

    def visit(current: BaseException) -> None:
        children = getattr(current, "exceptions", None)
        if isinstance(children, tuple) and children:
            for child in children:
                if isinstance(child, BaseException):
                    visit(child)
            return
        leaves.append(current)

    visit(exc)
    for leaf in leaves:
        if isinstance(leaf, UnscoreableTrialError):
            return leaf
    return leaves[0] if leaves else exc


def _configure_model(baseline: BaselineConfig) -> BaselineConfig:
    model = _required_env("MODEL")
    model_base_url = _required_env("MODEL_BASE_URL").rstrip("/")
    model_api_key = _runtime_model_api_key(_required_env("MODEL_API_KEY"))
    harbor_agent = os.environ.get("HARBOR_AGENT", "opencode").strip() or "opencode"
    provider = os.environ.get("MODEL_PROVIDER", "sglang").strip() or "sglang"
    model_api_protocol = (
        os.environ.get("MODEL_API_PROTOCOL", "openai").strip().lower() or "openai"
    )
    if model_api_protocol not in {"openai", "anthropic"}:
        raise ValueError(
            "MODEL_API_PROTOCOL must be 'openai' or 'anthropic'; "
            f"got {model_api_protocol!r}"
        )
    if harbor_agent not in {"codex", "opencode"}:
        raise ValueError(
            "The AP OpenAI-compatible runner supports HARBOR_AGENT='codex' "
            f"or 'opencode'; got {harbor_agent!r}"
        )
    if model_api_protocol == "anthropic" and harbor_agent != "opencode":
        raise ValueError(
            "MODEL_API_PROTOCOL='anthropic' currently requires HARBOR_AGENT='opencode'"
        )

    wire_api = os.environ.get("CODEX_WIRE_API", "responses").strip() or "responses"

    os.environ["OPENAI_BASE_URL"] = model_base_url
    os.environ["MODEL_API_KEY"] = model_api_key
    os.environ["OPENAI_API_KEY"] = model_api_key
    if model_api_protocol == "anthropic":
        os.environ["ANTHROPIC_BASE_URL"] = model_base_url
        os.environ["ANTHROPIC_API_KEY"] = model_api_key
    if harbor_agent == "codex":
        os.environ["CODEX_MODEL_PROVIDER"] = provider
        os.environ["CODEX_PROVIDER_ENV_KEY"] = "OPENAI_API_KEY"
        os.environ["CODEX_WIRE_API"] = wire_api

    # Legacy SkillAuthor/Judge/LLMSelfRetriever components run in the AP main
    # container rather than the Harbor task container. Same-session reflection
    # does not construct SkillAuthor; these variables remain useful for other
    # baselines and retrievers.
    litellm_prefix = "anthropic" if model_api_protocol == "anthropic" else "openai"
    os.environ["SEVB_HOST_LITELLM_MODEL"] = (
        model if "/" in model else f"{litellm_prefix}/{model}"
    )
    os.environ["SEVB_HOST_LITELLM_API_BASE"] = model_base_url
    os.environ["SEVB_HOST_LITELLM_API_KEY"] = model_api_key

    baseline_data = baseline.model_dump()
    baseline_data["harbor_agent_name"] = harbor_agent
    # Normalize the AP-facing convenience prefix away from the actual served
    # model id. OpenCode must use a non-reserved provider id: naming a generic
    # ``@ai-sdk/openai-compatible`` provider ``openai`` makes OpenCode select
    # its Responses-specific path instead of Chat Completions.
    served_model_id = model.removeprefix("openai/").removeprefix("anthropic/")
    baseline_data["model_name"] = (
        f"openai/{served_model_id}"
        if harbor_agent == "codex"
        else (
            f"anthropic/{served_model_id}"
            if model_api_protocol == "anthropic"
            else f"openai-compatible/{served_model_id}"
        )
    )
    agent_kwargs = dict(baseline_data.get("agent_kwargs") or {})
    for stale_key in (
        "api_base",
        "base_url",
        "provider",
        "env_key",
        "wire_api",
        "opencode_config",
        "version",
    ):
        agent_kwargs.pop(stale_key, None)

    if harbor_agent == "codex":
        # CodexPreinstalled consumes ``base_url``. Do not also populate
        # RunConfig.api_base: job_builder would add a second ``api_base``
        # kwarg, which the adapter passes to Harbor's Codex constructor.
        agent_kwargs.update(
            {
                "base_url": model_base_url,
                "provider": provider,
                "env_key": "OPENAI_API_KEY",
                "wire_api": wire_api,
            }
        )
    else:
        opencode_version = (
            os.environ.get("OPENCODE_VERSION", "1.18.3").strip() or "1.18.3"
        )
        # Keep the provider protocol explicit. The placeholders are resolved
        # in the task container, so Harbor config and AP artifacts never
        # contain the credential itself. Native Anthropic is required for
        # signed Claude reasoning blocks to survive same-session continuation.
        provider_id = (
            "anthropic" if model_api_protocol == "anthropic" else "openai-compatible"
        )
        provider_npm = (
            "@ai-sdk/anthropic"
            if model_api_protocol == "anthropic"
            else "@ai-sdk/openai-compatible"
        )
        base_url_env = (
            "ANTHROPIC_BASE_URL"
            if model_api_protocol == "anthropic"
            else "OPENAI_BASE_URL"
        )
        api_key_env = (
            "ANTHROPIC_API_KEY"
            if model_api_protocol == "anthropic"
            else "OPENAI_API_KEY"
        )
        agent_kwargs.update(
            {
                "version": opencode_version,
                "opencode_config": {
                    "$schema": "https://opencode.ai/config.json",
                    "autoupdate": False,
                    "snapshot": False,
                    "permission": "allow",
                    "provider": {
                        provider_id: {
                            "npm": provider_npm,
                            "name": provider,
                            "options": {
                                "baseURL": f"{{env:{base_url_env}}}",
                                "apiKey": f"{{env:{api_key_env}}}",
                            },
                            "models": {
                                served_model_id: {
                                    "name": served_model_id,
                                    "attachment": False,
                                    "limit": {
                                        "context": 131072,
                                        "output": 16384,
                                    },
                                }
                            },
                        }
                    },
                },
            }
        )
    baseline_data["agent_kwargs"] = agent_kwargs

    if "WITHIN_ENV_REPLAY" in os.environ:
        baseline_data["within_env_replay"] = _env_bool(
            "WITHIN_ENV_REPLAY", baseline.within_env_replay
        )
    if "REPLAY_EVAL" in os.environ:
        baseline_data["replay_eval"] = _env_bool("REPLAY_EVAL", baseline.replay_eval)
    if "LEARNING_MAX_ATTEMPTS" in os.environ:
        baseline_data["learning_max_attempts"] = _env_int(
            "LEARNING_MAX_ATTEMPTS",
            baseline.learning_max_attempts,
            minimum=1,
            maximum=5,
        )
    return BaselineConfig.model_validate(baseline_data)


def _build_config(output_dir: Path) -> RunConfig:
    environment_id = _required_env("INSTANCE_ID")
    if environment_id not in {f"E{i}" for i in range(1, 7)}:
        raise ValueError(
            f"INSTANCE_ID must select one environment E1..E6, got {environment_id!r}"
        )

    baseline_name = os.environ.get("BASELINE_NAME", "selfgen_in_session_always")
    baseline = _configure_model(load_baseline(baseline_name))
    strategy_name = os.environ.get("STRATEGY_NAME", baseline.default_strategy)
    if strategy_name == "none":
        strategy_name = "chain"
    strategy = StrategyConfig.from_yaml(
        REPO_ROOT / "configs" / "strategies" / f"{strategy_name}.yaml"
    )

    family_smoke_id = os.environ.get("SMOKE_FAMILY_ID", "").strip() or None
    max_tasks_raw = os.environ.get("SMOKE_MAX_TASKS", "").strip()
    max_tasks = int(max_tasks_raw) if max_tasks_raw else None
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    run_id = os.environ.get(
        "RUN_ID",
        f"ap__{baseline.name}__{environment_id}__{timestamp}",
    )
    workspace_override = os.environ.get("SEVB_WORKSPACE_ROOT", "").strip()
    if workspace_override:
        workspace_root = Path(workspace_override).expanduser()
        if not workspace_root.is_absolute():
            raise ValueError("SEVB_WORKSPACE_ROOT must be an absolute path")
        workspace_root = workspace_root.resolve()
    else:
        workspace_root = output_dir / "runs"
    return RunConfig(
        run_id=run_id,
        baseline=baseline,
        strategy=strategy,
        order_seed=os.environ.get("ORDER_SEED", "A"),
        environment_id=environment_id,
        family_smoke_id=family_smoke_id,
        workspace_root=workspace_root,
        # Host-side calls are routed by SEVB_HOST_LITELLM_* above. The Harbor
        # agent receives the endpoint through its agent-specific config/env.
        # Keeping this unset avoids duplicate base_url/api_base constructor
        # kwargs in skillevolbench.harbor_ext.job_builder.
        api_base=None,
        api_key_env_var="MODEL_API_KEY",
        harbor_agent_timeout_multiplier=_env_float(
            "HARBOR_AGENT_TIMEOUT_MULTIPLIER",
            1.0,
            minimum=1.0,
            maximum=4.0,
        ),
        max_tasks=max_tasks,
    )


def _success_metrics(config: RunConfig, report: Any) -> dict[str, Any]:
    task_success = report.task_success
    evolution = report.evolution_replay
    revision_safety = getattr(report, "revision_safety", {})
    reflection_transfer = getattr(report, "reflection_transfer", {}) or {}
    family_smoke = config.family_smoke_id is not None
    expected_primary = 6 if family_smoke else 30
    expected_replays = 0
    if not family_smoke and config.baseline.within_env_replay:
        expected_replays = 30 if config.baseline.replay_eval else 15
    expected_shadows = (
        (1 if family_smoke else 5) if config.baseline.dual_t6_retrieval else 0
    )
    n_verifier_backed_trials = (
        report.n_primary_trials + report.n_replay_trials + report.n_shadow_trials
    )
    unit_complete = (
        config.max_tasks is None
        and report.n_primary_trials == expected_primary
        and report.n_replay_trials == expected_replays
        and report.n_shadow_trials == expected_shadows
    )
    reflection = getattr(report, "reflection", {}) or {}
    expected_reflections = 0
    if config.baseline.skill_update_source == "same_agent_session":
        # A family smoke has one family x T1-T3; a canonical environment has
        # five. Both require a terminal same-session result for every learning
        # primary trial before the execution unit is considered complete.
        expected_reflections = 3 if family_smoke else 15
        unit_complete = (
            unit_complete and reflection.get("n_terminal") == expected_reflections
        )
        unit_complete = unit_complete and (
            reflection.get("n_same_session_verified") == reflection.get("n_attempted")
        )
        unit_complete = unit_complete and (
            reflection.get("n_all_attempts_same_session_verified")
            == reflection.get("n_terminal")
        )
    canonical_complete = bool(unit_complete and not family_smoke)
    evaluation_sr = float(task_success.get("evaluation_sr", 0.0))
    metrics: dict[str, Any] = {
        "task_score": evaluation_sr if canonical_complete else 0.0,
        "passed": bool(canonical_complete and evaluation_sr == 1.0),
        "status": (
            "completed"
            if canonical_complete
            else ("completed_noncanonical" if unit_complete else "partial")
        ),
        "scoreable": canonical_complete,
        "canonical": not family_smoke and config.max_tasks is None,
        "execution_scope": (
            "family_smoke"
            if family_smoke
            else ("truncated_smoke" if config.max_tasks is not None else "environment")
        ),
        "environment_id": config.environment_id,
        "family_smoke_id": config.family_smoke_id,
        "run_id": config.run_id,
        "baseline_name": config.baseline.name,
        "evaluation_sr": evaluation_sr,
        "learning_sr": float(task_success.get("learning_sr", 0.0)),
        "t4_transfer": float(task_success.get("t4_transfer", 0.0)),
        "t5_trap_resistance": float(task_success.get("t5_trap_resistance", 0.0)),
        "t6_composition_rate": float(task_success.get("t6_composition_rate", 0.0)),
        "n_primary_trials": report.n_primary_trials,
        "expected_primary_trials": expected_primary,
        "n_replay_trials": report.n_replay_trials,
        "expected_replay_trials": expected_replays,
        "n_shadow_trials": report.n_shadow_trials,
        "expected_shadow_trials": expected_shadows,
        "n_verifier_backed_trials": n_verifier_backed_trials,
        "expected_verifier_backed_trials": (
            expected_primary + expected_replays + expected_shadows
        ),
        "evolution_lift": evolution.get("evolution_lift"),
        "recovery_rate": evolution.get("recovery_rate"),
        "regression_rate": evolution.get("regression_rate"),
        "fail_to_success_count": evolution.get("fail_to_success_count", 0),
        "success_to_fail_count": evolution.get("success_to_fail_count", 0),
        "cross_task_revision_pairs": revision_safety.get(
            "n_cross_task_revision_pairs", 0
        ),
        "cross_task_fail_to_success_count": revision_safety.get(
            "fail_to_success_count", 0
        ),
        "cross_task_fail_to_fail_count": revision_safety.get("fail_to_fail_count", 0),
        "cross_task_success_to_success_count": revision_safety.get(
            "success_to_success_count", 0
        ),
        "cross_task_success_to_fail_count": revision_safety.get(
            "success_to_fail_count", 0
        ),
        "reflection_enabled": bool(reflection.get("enabled", False)),
        "learning_max_attempts": config.baseline.learning_max_attempts,
        "learning_attempts_total": reflection.get("learning_attempts_total", 0),
        "repair_attempts_total": reflection.get("repair_attempts_total", 0),
        "initial_learning_pass_count": reflection.get("initial_learning_pass_count", 0),
        "terminal_learning_pass_count": reflection.get(
            "terminal_learning_pass_count", 0
        ),
        "repaired_to_pass_count": reflection.get("repaired_to_pass_count", 0),
        "same_task_repair_success_rate": reflection.get(
            "same_task_repair_success_rate"
        ),
        "n_reflection_expected": expected_reflections,
        "n_reflection_terminal": reflection.get("n_terminal", 0),
        "n_reflection_attempted": reflection.get("n_attempted", 0),
        "n_reflection_completed": reflection.get("n_completed", 0),
        "n_reflection_noop": reflection.get("n_noop", 0),
        "n_reflection_rejected": reflection.get("n_rejected", 0),
        "n_reflection_agent_timeouts": reflection.get("n_agent_timeouts", 0),
        "n_same_session_verified": reflection.get("n_same_session_verified", 0),
        "n_all_attempts_same_session_verified": reflection.get(
            "n_all_attempts_same_session_verified", 0
        ),
        "reflection_valid_output_rate": reflection.get("valid_output_rate"),
        "reflection_patch_candidate_rate": reflection.get("patch_candidate_rate"),
        "reflection_noop_rate": reflection.get("noop_rate"),
        "reflection_rejection_rate": reflection.get("rejection_rate"),
        "reflection_transfer_pairs": reflection_transfer.get("n_pairs", 0),
        "reflection_fail_to_success_count": reflection_transfer.get(
            "fail_to_success_count", 0
        ),
        "reflection_fail_to_fail_count": reflection_transfer.get(
            "fail_to_fail_count", 0
        ),
        "reflection_success_to_success_count": reflection_transfer.get(
            "success_to_success_count", 0
        ),
        "reflection_success_to_fail_count": reflection_transfer.get(
            "success_to_fail_count", 0
        ),
        "reflection_failure_recovery_rate": reflection_transfer.get(
            "failure_recovery_rate"
        ),
        "reflection_success_regression_rate": reflection_transfer.get(
            "success_regression_rate"
        ),
        "cross_task_failure_recovery_rate": revision_safety.get(
            "failure_recovery_rate"
        ),
        "cross_task_success_regression_rate": revision_safety.get(
            "success_regression_rate"
        ),
    }
    if family_smoke and unit_complete:
        metrics["message"] = (
            "Complete T1-T6 single-family smoke; intentionally non-canonical "
            "and unscoreable as a benchmark result."
        )
    elif not canonical_complete:
        metrics["message"] = (
            "Partial infrastructure smoke; task_score is intentionally zero "
            "and must not be aggregated as a benchmark result."
        )
    return metrics


def main() -> int:
    output_dir = Path(os.environ.get("OUTPUT_DIR", "/tmp/output")).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics_path = output_dir / "metrics.json"

    try:
        config = _build_config(output_dir)
        _write_json(
            output_dir / "ap_run_manifest.json",
            {
                "schema_version": "1.0",
                "benchmark_revision": _safe_git_revision(),
                "run_id": config.run_id,
                "environment_id": config.environment_id,
                "family_smoke_id": config.family_smoke_id,
                "execution_scope": (
                    "family_smoke"
                    if config.family_smoke_id is not None
                    else (
                        "truncated_smoke"
                        if config.max_tasks is not None
                        else "environment"
                    )
                ),
                "canonical": (
                    config.family_smoke_id is None and config.max_tasks is None
                ),
                "baseline_name": config.baseline.name,
                "strategy_name": config.strategy.name,
                "order_seed": config.order_seed,
                "model": os.environ["MODEL"],
                "model_base_url": os.environ["MODEL_BASE_URL"],
                "model_api_protocol": os.environ.get("MODEL_API_PROTOCOL", "openai"),
                "harbor_agent": config.baseline.harbor_agent_name,
                "within_env_replay": config.baseline.within_env_replay,
                "replay_eval": config.baseline.replay_eval,
                "learning_max_attempts": config.baseline.learning_max_attempts,
                "harbor_agent_timeout_multiplier": (
                    config.harbor_agent_timeout_multiplier
                ),
                "smoke_max_tasks": config.max_tasks,
                "workspace_root": str(config.workspace_root),
                "started_at": datetime.now(timezone.utc).isoformat(),
            },
        )
        report = asyncio.run(LifelongRunner(config).run())
        _write_json(metrics_path, _success_metrics(config, report))
        return 0
    except Exception as exc:
        actionable = _actionable_exception(exc)
        failed_family_smoke_id = os.environ.get("SMOKE_FAMILY_ID") or None
        failed_max_tasks = os.environ.get("SMOKE_MAX_TASKS") or None
        _write_json(
            metrics_path,
            {
                "task_score": 0.0,
                "passed": False,
                "status": "failed",
                "scoreable": False,
                "canonical": not failed_family_smoke_id and not failed_max_tasks,
                "execution_scope": (
                    "family_smoke"
                    if failed_family_smoke_id
                    else ("truncated_smoke" if failed_max_tasks else "environment")
                ),
                "environment_id": os.environ.get("INSTANCE_ID"),
                "family_smoke_id": failed_family_smoke_id,
                "expected_primary_trials": 6 if failed_family_smoke_id else 30,
                "n_primary_trials": 0,
                "n_verifier_backed_trials": 0,
                "error_type": type(actionable).__name__,
                "message": _sanitize_error(str(actionable)),
            },
        )
        # Never emit the raw exception traceback: SDK errors often include
        # request headers or URLs containing credentials. Keep the traceback
        # useful for AP debugging, but apply the same credential redaction as
        # the persisted failure metric first.
        print(_sanitize_error(traceback.format_exc()), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
