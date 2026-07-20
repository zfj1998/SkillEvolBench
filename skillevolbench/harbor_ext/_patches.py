"""Runtime compatibility patches for Harbor instruction injection.

Harbor reads ``instruction.md`` while constructing a ``Task``, before the
``TrialEvent.START`` hook fires.  SkillEvolBench's START hook then writes the
retrieval-augmented instruction to disk, so Harbor's cached instruction must
be refreshed immediately before agent execution.

The private execution API changed across supported Harbor releases:

* older releases execute through ``Trial._execute_agent`` and store the task
  on ``self._task``;
* Harbor 0.7+ executes through ``Trial._run_agent_phase``; newer releases
  store the task on ``self.task`` instead of ``self._task``.

The same-session lifecycle is intentionally pinned to Harbor 0.20.0 at Git
revision ``071281b3d931aafd6a5375fa7d5933e23054d784``.  It copies private
Harbor execution code, so enabling that seam first verifies both the package
version and the exact callable shapes it relies on.  Multi-step calls are
deliberately left untouched: their per-step instructions are read separately,
and SkillEvolBench currently contains only single-step tasks.
"""

from __future__ import annotations

import asyncio
import inspect
import json
import logging
from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any


_LOG = logging.getLogger(__name__)
_PATCHED: bool = False
_POST_VERIFIER_PATCHED: bool = False
_POST_VERIFIER_CALLBACK: Callable[[Any], Awaitable[None]] | None = None

_SUPPORTED_HARBOR_VERSION = "0.20.0"
_PINNED_HARBOR_REVISION = "071281b3d931aafd6a5375fa7d5933e23054d784"


def _parameter_shape(callable_obj: Callable[..., Any]) -> tuple[tuple[str, str, str], ...]:
    """Return the annotation-independent shape of one private callable."""
    shape: list[tuple[str, str, str]] = []
    for parameter in inspect.signature(callable_obj).parameters.values():
        default = (
            "<required>"
            if parameter.default is inspect.Parameter.empty
            else repr(parameter.default)
        )
        shape.append((parameter.name, parameter.kind.name, default))
    return tuple(shape)


_EXPECTED_PRIVATE_SIGNATURES: dict[str, tuple[tuple[str, str, str], ...]] = {
    "Trial._run_agent_phase": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("target", "KEYWORD_ONLY", "<required>"),
        ("instruction", "KEYWORD_ONLY", "<required>"),
        ("timeout_sec", "KEYWORD_ONLY", "<required>"),
        ("user", "KEYWORD_ONLY", "<required>"),
        ("step_cfg", "KEYWORD_ONLY", "None"),
        ("resume", "KEYWORD_ONLY", "False"),
    ),
    "SingleStepTrial._run": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
    ),
    "SingleStepTrial._run_agent": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
    ),
    "SingleStepTrial._upload_agent_logs": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
    ),
    "SingleStepTrial._collect_artifacts": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("stop_main_before_sidecars", "KEYWORD_ONLY", "False"),
    ),
    "SingleStepTrial._separate_verifier_env": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("env_config", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("key", "KEYWORD_ONLY", "<required>"),
        ("plan", "KEYWORD_ONLY", "<required>"),
        ("step_cfg", "KEYWORD_ONLY", "None"),
    ),
    "SingleStepTrial._stop_agent_environment": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
    ),
    "SingleStepTrial._network_plan": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("step_cfg", "POSITIONAL_OR_KEYWORD", "None"),
        ("env_config", "KEYWORD_ONLY", "None"),
    ),
    "SingleStepTrial._phase_network_policy": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("environment", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("baseline_policy", "KEYWORD_ONLY", "<required>"),
        ("phase_policy", "KEYWORD_ONLY", "<required>"),
    ),
    "SingleStepTrial._log_context": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("phase", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("environment", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("step_name", "POSITIONAL_OR_KEYWORD", "None"),
    ),
    "SingleStepTrial._emit": (
        ("self", "POSITIONAL_OR_KEYWORD", "<required>"),
        ("event", "POSITIONAL_OR_KEYWORD", "<required>"),
    ),
}


def _assert_supported_harbor_private_api(
    trial_class: type[Any], single_step_class: type[Any]
) -> None:
    """Fail before monkey-patching when the pinned Harbor contract drifted.

    ``harbor.__version__`` is also convenient for lightweight test doubles,
    avoiding a dependency on installed-distribution metadata in unit tests.
    """
    import harbor

    actual_version = getattr(harbor, "__version__", None)
    if actual_version != _SUPPORTED_HARBOR_VERSION:
        raise RuntimeError(
            "Unsupported Harbor runtime for same-session reflection: expected "
            f"harbor=={_SUPPORTED_HARBOR_VERSION} from "
            f"{_PINNED_HARBOR_REVISION}, got {actual_version!r}"
        )

    callables = {
        "Trial._run_agent_phase": getattr(trial_class, "_run_agent_phase"),
        **{
            f"SingleStepTrial.{name}": getattr(single_step_class, name)
            for name in (
                "_run",
                "_run_agent",
                "_upload_agent_logs",
                "_collect_artifacts",
                "_separate_verifier_env",
                "_stop_agent_environment",
                "_network_plan",
                "_phase_network_policy",
                "_log_context",
                "_emit",
            )
        },
    }
    mismatches: list[str] = []
    for label, expected in _EXPECTED_PRIVATE_SIGNATURES.items():
        actual = _parameter_shape(callables[label])
        if actual != expected:
            mismatches.append(f"{label}: expected {expected!r}, got {actual!r}")
    if mismatches:
        raise RuntimeError(
            "Pinned Harbor private API signatures changed; refusing to install "
            "the same-session lifecycle patch:\n" + "\n".join(mismatches)
        )


def _refresh_instruction(self: Any, strip_canary: Callable[[str], str]) -> str | None:
    """Refresh and return a trial's cached single-step instruction."""
    task = getattr(self, "task", None)
    if task is None:
        task = getattr(self, "_task", None)
    if task is None:
        raise RuntimeError("Harbor trial does not expose task or _task")
    if getattr(task, "has_steps", False):
        return None

    paths = getattr(task, "paths", None)
    instruction_path = getattr(paths, "instruction_path", None)
    if instruction_path is None:
        raise RuntimeError("Harbor task does not expose paths.instruction_path")
    if not instruction_path.is_file():
        raise FileNotFoundError(
            f"Harbor instruction file disappeared before agent execution: "
            f"{instruction_path}"
        )

    fresh = strip_canary(instruction_path.read_text())
    append_extra = getattr(task, "_append_extra_instructions", None)
    if callable(append_extra):
        fresh = append_extra(fresh)
    task.instruction = fresh
    return fresh


def _validate_task_snapshot(trial: Any) -> Path:
    """Validate Harbor's best-effort artifact result as a grading boundary."""
    artifacts_dir = Path(trial.paths.artifacts_dir)
    manifest_path = artifacts_dir / "manifest.json"
    try:
        manifest = json.loads(manifest_path.read_text())
    except Exception as exc:
        raise RuntimeError(
            "isolated verifier requires a readable artifacts/manifest.json"
        ) from exc
    if not isinstance(manifest, list):
        raise RuntimeError("artifacts/manifest.json must contain a JSON list")

    matches = [
        entry
        for entry in manifest
        if isinstance(entry, dict) and entry.get("source") == "/root/task"
    ]
    if len(matches) != 1:
        raise RuntimeError(
            "isolated verifier requires exactly one /root/task manifest entry; "
            f"found {len(matches)}"
        )
    entry = matches[0]
    expected = {
        "destination": "artifacts/root/task",
        "status": "ok",
    }
    mismatches = {
        key: (entry.get(key), value)
        for key, value in expected.items()
        if entry.get(key) != value
    }
    # Harbor 0.20 determines this field with ``service_is_dir`` before the
    # transfer.  Once the main container is stopped that exec-based probe
    # returns false, while ``docker compose cp`` still copies /root/task as a
    # directory.  Treat the field as a transfer-branch marker and the
    # no-follow host check below as the authoritative object type.
    if entry.get("type") not in ("directory", "file"):
        mismatches["type"] = (
            entry.get("type"),
            "'directory' or stopped-container fallback 'file'",
        )
    if entry.get("service") not in (None, "main"):
        mismatches["service"] = (entry.get("service"), None)
    if mismatches:
        raise RuntimeError(
            "invalid /root/task artifact manifest entry: "
            + ", ".join(
                f"{key}={actual!r} (expected {wanted!r})"
                for key, (actual, wanted) in mismatches.items()
            )
        )

    snapshot = artifacts_dir / "root" / "task"
    if snapshot.is_symlink() or not snapshot.is_dir():
        raise RuntimeError(
            "isolated verifier task snapshot is missing or not a real directory: "
            f"{snapshot}"
        )
    try:
        has_contents = next(snapshot.iterdir(), None) is not None
    except OSError as exc:
        raise RuntimeError(
            f"cannot inspect isolated verifier task snapshot: {snapshot}"
        ) from exc
    if not has_contents:
        raise RuntimeError(
            f"isolated verifier task snapshot is empty: {snapshot}"
        )
    trial._sevb_task_snapshot_path = snapshot
    return snapshot


async def _running_main_identity(trial: Any) -> str:
    """Query running state through the benchmark environment, fail closed."""
    running_identity = getattr(
        trial.agent_environment, "main_service_running_identity", None
    )
    if not callable(running_identity):
        raise RuntimeError(
            "same-session environment cannot prove whether main is running"
        )
    try:
        value = await running_identity()
    except Exception as exc:
        raise RuntimeError("failed to query running main container identity") from exc
    if not isinstance(value, str):
        raise RuntimeError(
            "main_service_running_identity() returned a non-string value"
        )
    return value.strip()


async def _stop_main_and_prove(trial: Any, *, phase: str) -> None:
    """Stop ``main`` and independently prove no main container is running."""
    stop_error: BaseException | None = None
    try:
        await trial.agent_environment.stop_service("main")
    except BaseException as exc:
        stop_error = exc

    running = await _running_main_identity(trial)
    if running:
        error = RuntimeError(
            f"main container still running after {phase} stop: {running}"
        )
        if stop_error is not None:
            raise error from stop_error
        raise error

    trial._sevb_agent_main_stopped = True
    if stop_error is not None:
        trial.logger.warning(
            "main stop raised during %s, but an independent compose query "
            "proved there is no running main container: %s",
            phase,
            stop_error,
        )
        if isinstance(stop_error, asyncio.CancelledError):
            raise stop_error


async def _secure_stop_agent_environment(trial: Any) -> None:
    """Clean up without trusting Harbor's best-effort stop bookkeeping."""
    pre_cleanup_error: BaseException | None = None
    try:
        await _stop_main_and_prove(trial, phase="pre-cleanup")
    except BaseException as exc:
        # Continue into Harbor cleanup: it may still delete a container that a
        # first compose stop/query could not reach.
        pre_cleanup_error = exc

    harbor_cleanup_error: BaseException | None = None
    try:
        await trial._stop_agent_environment()
    except BaseException as exc:
        harbor_cleanup_error = exc

    # Harbor 0.20 records cleanup exceptions and returns. Query independently
    # after that call, and issue one more explicit stop, so a swallowed error
    # cannot leave a verifier-aware agent process alive.
    try:
        await _stop_main_and_prove(trial, phase="post-cleanup")
    except asyncio.CancelledError:
        # _stop_main_and_prove re-raises cancellation only after the running
        # state query proved cleanup safety.
        raise
    except BaseException as exc:
        raise RuntimeError(
            "could not prove the main agent container stopped during cleanup"
        ) from exc

    for label, error in (
        ("pre-cleanup", pre_cleanup_error),
        ("Harbor cleanup", harbor_cleanup_error),
    ):
        if error is not None:
            trial.logger.warning(
                "%s raised, but the final independent running-state check "
                "proved main is stopped: %s",
                label,
                error,
            )
    cancellation = next(
        (
            error
            for error in (pre_cleanup_error, harbor_cleanup_error)
            if isinstance(error, asyncio.CancelledError)
        ),
        None,
    )
    if cancellation is not None:
        raise cancellation


async def _run_isolated_verifier(trial: Any) -> None:
    """Grade the stopped agent container's validated /root/task snapshot.

    This is deliberately an exact-version compatibility copy of Harbor
    0.20's separate-verifier path with two differences: the verifier is built
    from the original ``environment/`` image and hidden tests are uploaded
    only into that clean verifier container.
    """
    from harbor.models.trial.paths import EnvironmentPaths
    from harbor.models.trial.result import TimingInfo
    from harbor.trial.errors import VerifierTimeoutError
    from harbor.trial.hooks import TrialEvent
    from harbor.verifier.factory import VerifierFactory

    if trial.config.verifier.disable:
        raise RuntimeError("same-session reflection requires the official verifier")

    await trial._emit(TrialEvent.VERIFICATION_START)
    trial.result.verifier = TimingInfo(started_at=trial._now())
    user = trial.task.config.verifier.user

    # _separate_verifier_env normally builds from tests/. Our benchmark tests
    # dirs intentionally have no Dockerfile. Use the clean task environment,
    # then let Verifier upload tests to /tests after /root/task is restored.
    had_override = "_verifier_env_build_context" in trial.__dict__
    previous_override = trial.__dict__.get("_verifier_env_build_context")
    trial._verifier_env_build_context = (
        lambda _step_cfg: trial.task.paths.environment_dir
    )
    try:
        env_config = trial.task.config.environment.model_copy(deep=True)
        plan = trial._network_plan(env_config=env_config)
        async with trial._separate_verifier_env(
            env_config,
            key="sevb-isolated",
            plan=plan,
        ) as target_env:
            with target_env.with_default_user(user):
                env_paths = EnvironmentPaths.for_os(target_env.os)
                await target_env.empty_dirs([env_paths.verifier_dir], chmod=True)
                await trial._artifact_handler.upload_artifacts(
                    target_env,
                    artifacts_dir=trial.paths.artifacts_dir,
                    source_artifacts_dir=trial.agent_env_paths.artifacts_dir,
                    target_artifacts_dir=env_paths.artifacts_dir,
                )
                verifier = VerifierFactory.create_verifier_from_config(
                    trial.config.verifier,
                    task=trial.task,
                    trial_paths=trial.paths,
                    environment=target_env,
                    override_env=trial.config.verifier.env or None,
                    logger=trial.logger,
                    verifier_env=None,
                    step_name=None,
                    skip_tests_upload=False,
                )
                verifier_env_baseline = plan.verifier_env_baseline
                if verifier_env_baseline is None:
                    raise RuntimeError("isolated verifier has no network baseline")
                async with trial._phase_network_policy(
                    target_env,
                    baseline_policy=verifier_env_baseline,
                    phase_policy=plan.verifier_phase,
                ):
                    with trial._log_context("verification", target_env, None):
                        trial.result.verifier_result = await asyncio.wait_for(
                            verifier.verify(), timeout=trial._verifier_timeout_sec
                        )
    except asyncio.TimeoutError as exc:
        raise VerifierTimeoutError(
            "Verifier execution timed out after "
            f"{trial._verifier_timeout_sec} seconds"
        ) from exc
    finally:
        if had_override:
            trial._verifier_env_build_context = previous_override
        else:
            del trial.__dict__["_verifier_env_build_context"]
        trial.result.verifier.finished_at = trial._now()


def apply_harbor_patches() -> None:
    """Install the instruction-refresh patch once for a Harbor process."""
    global _PATCHED
    if _PATCHED:
        return

    # Keep Harbor optional at module import time so the rest of the benchmark
    # remains unit-testable without the SDK installed.
    from harbor.models.task.task import strip_canary
    from harbor.trial.trial import Trial

    try:
        from harbor.trial.single_step import SingleStepTrial
    except ImportError:
        SingleStepTrial = None  # type: ignore[assignment,misc]

    required = (
        "_run",
        "_run_agent",
        "_upload_agent_logs",
        "_collect_artifacts",
        "_separate_verifier_env",
        "_stop_agent_environment",
        "_network_plan",
        "_phase_network_policy",
        "_log_context",
        "_emit",
    )
    supports_isolated_reflection = SingleStepTrial is not None and all(
        hasattr(SingleStepTrial, name) for name in required
    )
    if supports_isolated_reflection:
        # Assert before modifying either class so a mismatch cannot leave a
        # half-installed process-level patch behind.
        _assert_supported_harbor_private_api(Trial, SingleStepTrial)

    if hasattr(Trial, "_run_agent_phase"):
        # Harbor 0.7+ passes the cached instruction as a keyword argument.
        # ``_refresh_instruction`` checks Task.has_steps rather than relying on
        # the newer ``step_cfg`` parameter, which did not exist in Harbor 0.7.
        original_run_agent_phase = Trial._run_agent_phase

        async def _run_agent_phase_with_fresh_instruction(
            self: Any, *args: Any, **kwargs: Any
        ) -> None:
            # A resumed phase deliberately carries a new follow-up prompt
            # (post-verifier reflection). Re-reading instruction.md here would
            # replace it with the original task and run the solve twice.
            if kwargs.get("resume", False):
                await original_run_agent_phase(self, *args, **kwargs)
                return
            try:
                fresh = _refresh_instruction(self, strip_canary)
                if fresh is not None:
                    if "instruction" not in kwargs:
                        raise RuntimeError(
                            "Harbor _run_agent_phase did not receive instruction "
                            "as a keyword argument"
                        )
                    kwargs["instruction"] = fresh
            except Exception as exc:
                raise RuntimeError(
                    "Harbor instruction refresh failed; refusing to run the "
                    "agent with a stale pre-hook prompt"
                ) from exc
            await original_run_agent_phase(self, *args, **kwargs)

        Trial._run_agent_phase = _run_agent_phase_with_fresh_instruction
        patched_api = "Trial._run_agent_phase"

    elif hasattr(Trial, "_execute_agent"):
        # Legacy Harbor path.  Refreshing ``self._task.instruction`` is enough
        # because the original method reads that attribute after this wrapper.
        original_execute_agent = Trial._execute_agent

        async def _execute_agent_with_fresh_instruction(self: Any) -> None:
            try:
                _refresh_instruction(self, strip_canary)
            except Exception as exc:
                raise RuntimeError(
                    "Harbor instruction refresh failed; refusing to run the "
                    "agent with a stale pre-hook prompt"
                ) from exc
            await original_execute_agent(self)

        Trial._execute_agent = _execute_agent_with_fresh_instruction
        patched_api = "Trial._execute_agent"

    else:
        raise RuntimeError(
            "Unsupported Harbor Trial API: expected _execute_agent or "
            "_run_agent_phase. Pin a supported Harbor revision or update "
            "skillevolbench.harbor_ext._patches."
        )

    # Harbor 0.20's stock shared verifier exposes /tests to the agent
    # container, while stock separate mode destroys that container before the
    # verifier runs. Same-session reflection needs a third, exact lifecycle:
    # stop (not delete) the agent container, snapshot the task, grade the
    # snapshot in a clean verifier container, then restart the original
    # container and resume its OpenCode session. The registered callback owns
    # the restart/reflection step. Ordinary baselines keep Harbor's original
    # lifecycle byte-for-byte.
    global _POST_VERIFIER_PATCHED
    try:
        from harbor.trial.single_step import SingleStepTrial
    except ImportError:
        # Older supported Harbor test doubles do not expose SingleStepTrial.
        # They can still use instruction refresh, but same-session reflection
        # will fail its explicit support check before a job runs.
        _LOG.debug("harbor_ext: SingleStepTrial unavailable; no post-verifier seam")
    else:
        required = (
            "_run",
            "_run_agent",
            "_upload_agent_logs",
            "_collect_artifacts",
            "_separate_verifier_env",
            "_stop_agent_environment",
        )
        missing = [name for name in required if not hasattr(SingleStepTrial, name)]
        if missing or not supports_isolated_reflection:
            _LOG.debug(
                "harbor_ext: SingleStepTrial lacks isolated-reflection APIs: %s",
                missing or "signature-check prerequisites",
            )
        else:
            original_single_step_run = SingleStepTrial._run
            # Capture the module helper so focused tests can replace the
            # isolated verifier without fabricating Harbor internals.
            isolated_verifier_runner = _run_isolated_verifier

            async def _run_with_isolated_reflection(self: Any) -> None:
                callback = _POST_VERIFIER_CALLBACK
                if callback is None:
                    await original_single_step_run(self)
                    return

                # The benchmark scheduler is single-trial. Keeping this check
                # local makes an accidental provider/config change fail closed
                # instead of silently falling back to shared hidden tests.
                if getattr(self.task, "has_steps", False):
                    raise RuntimeError(
                        "same-session reflection supports single-step tasks only"
                    )
                artifacts = [
                    getattr(item, "source", item)
                    for item in (
                        list(getattr(self.task.config, "artifacts", []))
                        + list(getattr(self.config, "artifacts", []))
                    )
                ]
                if artifacts.count("/root/task") != 1:
                    raise RuntimeError(
                        "isolated verifier requires exactly one /root/task artifact"
                    )

                try:
                    await self._run_agent()
                    await self._upload_agent_logs()

                    # Kill every solve-turn process before hidden tests or raw
                    # verifier logs exist. Docker compose stop preserves the
                    # writable layer and host-mounted OpenCode session state.
                    identity_fn = getattr(
                        self.agent_environment, "main_service_identity", None
                    )
                    if not callable(identity_fn):
                        raise RuntimeError(
                            "same-session environment cannot prove container identity"
                        )
                    identity = await identity_fn()
                    if not isinstance(identity, str) or not identity.strip():
                        raise RuntimeError(
                            "same-session environment returned an empty container id"
                        )
                    if len(identity.splitlines()) != 1:
                        raise RuntimeError(
                            "same-session environment returned multiple main containers"
                        )
                    self._sevb_agent_container_identity = identity.strip()

                    # A successful stop call alone is not evidence. Query the
                    # running service set before any hidden verifier state is
                    # allowed to exist.
                    await _stop_main_and_prove(self, phase="pre-verifier")

                    # docker cp works for a stopped container, so this is an
                    # immutable grading snapshot even if the solve spawned a
                    # background writer.
                    await self._collect_artifacts(
                        stop_main_before_sidecars=False
                    )
                    _validate_task_snapshot(self)
                    await isolated_verifier_runner(self)
                    await callback(self)
                finally:
                    await _secure_stop_agent_environment(self)

            SingleStepTrial._run = _run_with_isolated_reflection
            _POST_VERIFIER_PATCHED = True

    _PATCHED = True
    _LOG.info(
        "harbor_ext: patched %s to refresh task.instruction before agent.run",
        patched_api,
    )


def register_post_verifier_callback(
    callback: Callable[[Any], Awaitable[None]],
) -> None:
    """Register the one benchmark callback used by the current Harbor job."""
    global _POST_VERIFIER_CALLBACK
    if not _POST_VERIFIER_PATCHED:
        raise RuntimeError(
            "Pinned Harbor does not expose the post-verifier single-step seam; "
            "same-agent-session reflection cannot preserve the live container"
        )
    if _POST_VERIFIER_CALLBACK is not None:
        raise RuntimeError("a post-verifier callback is already registered")
    _POST_VERIFIER_CALLBACK = callback


def clear_post_verifier_callback() -> None:
    """Remove job-owned state while leaving the process-level patch installed."""
    global _POST_VERIFIER_CALLBACK
    _POST_VERIFIER_CALLBACK = None


__all__ = [
    "apply_harbor_patches",
    "register_post_verifier_callback",
    "clear_post_verifier_callback",
]
