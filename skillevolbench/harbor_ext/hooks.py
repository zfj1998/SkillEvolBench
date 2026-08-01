"""``SkillEvolBenchHooks`` -- the protocol's nervous system (Part 4 §4.2).

Two async hooks register with ``harbor.Job``:

* ``on_trial_started`` -- before container start. Performs curated injection
                          (Path B), zero-shot induction (Self-Gen-Zero-Shot),
                          env transition + freeze, retrieval, runtime build.
* ``on_trial_ended``   -- after verifier completes. Parses outcome, persists
                          ReplayRecord, and (in learning blocks) dispatches
                          to ``strategy.decide()``.

This module **does not** import Harbor at module load. Harbor's
``TrialHookEvent`` type is imported under ``TYPE_CHECKING`` so the hook
class is unit-testable on machines without the Harbor SDK. The hook
forwards calls to a ``RuntimeProtocol`` (Part 4 ``types.py``) -- Part 8's
``BaselineRuntime`` is the concrete implementer.

The flow tracks Engineering Design §4.2 verbatim. Methods ending in ``_`` are
internal hooks for unit-test seams.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import shutil
import stat
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING, Any, Callable

from skillevolbench.components.in_session_reflection import (
    InSessionSkillReflection,
    REFLECTION_AGENT_TIMEOUT_REASON,
    REFLECTION_CANDIDATE_FILENAME,
    REFLECTION_FEEDBACK_FILENAME,
    REFLECTION_PROMPT_FILENAME,
    REFLECTION_RESULT_FILENAME,
    REPAIR_AUDIT_DIRNAME,
    ReflectionCandidateError,
    ReflectionRecord,
)
from skillevolbench.components.verifier_adapter import UnscoreableTrialError
from skillevolbench.opencode_continuity import (
    OPENCODE_AUTO_COMPACTION_KIND,
    OPENCODE_COMPACTION_CONTINUE_KIND,
    OPENCODE_COMPACTION_SUMMARY_KIND,
    OPENCODE_EVENT_KEY,
    OPENCODE_POST_COMPACTION_ASSISTANT_KIND,
    opencode_synthetic_continue,
)
from skillevolbench.schemas import TaskRole

if TYPE_CHECKING:
    # These types only need to exist at type-check time. They are NOT
    # imported at runtime to keep this module Harbor-free at import.
    from harbor.trial.hooks import TrialHookEvent  # type: ignore

    from skillevolbench.harbor_ext.types import (
        RuntimeProtocol,
        TaskRegistryProtocol,
        RuntimeBuilderProtocol,
        PromptBuilderProtocol,
    )


_LOG = logging.getLogger(__name__)


_LEARNING_ROLES = {TaskRole.CANONICAL, TaskRole.ENRICHED, TaskRole.VARIANT}
_EVAL_ROLES = {TaskRole.CONTEXT_SHIFT, TaskRole.ADVERSARIAL, TaskRole.COMPOSITION}


# Keep in sync with skillevolbench.harbor_ext.job_builder.SHADOW_T6_SUFFIX
# and REPLAY_SUFFIX. Duplicated here to avoid an import cycle.
_SHADOW_T6_SUFFIX = "__oracle_shadow"
_REPLAY_SUFFIX = "__replay"

_AUDIT_DIRNAME = "self-reflection-audit"
_MAX_AUDIT_FILE_BYTES = 64 * 1024 * 1024
_MAX_CANDIDATE_BYTES = 1_000_000
_REFLECTION_EXPORT_TIMEOUT_SEC = 60


def _is_agent_timeout_error(exc: BaseException) -> bool:
    """Recognize Harbor's timeout without importing Harbor at module load."""

    try:
        from harbor.trial.errors import AgentTimeoutError  # type: ignore
    except ImportError:
        return False
    return isinstance(exc, AgentTimeoutError)


def _is_shadow_trial_name(raw: str) -> bool:
    """A dual-T6 shadow trial's runtime dir basename ends with the suffix.

    Use ``endswith`` not ``in``: a substring check would misclassify any
    future task whose name happens to contain the literal "__oracle_shadow"
    as a shadow trial. The suffix is appended at the end by job_builder
    when building the shadow runtime dir, so endswith is the precise
    invariant.
    """
    return raw.endswith(_SHADOW_T6_SUFFIX)


def _is_replay_trial_name(raw: str) -> bool:
    """A within-env replay trial's runtime dir basename ends with the suffix."""
    return raw.endswith(_REPLAY_SUFFIX)


class SkillEvolBenchHooks:
    """Trial-lifecycle hooks driving the lifelong protocol.

    The hook is owned by Part 9's ``LifelongRunner`` -- it constructs the
    runtime + registry + builders, then registers the hook on the
    ``harbor.Job``. After registration, all hook activity is driven by
    Harbor's per-trial dispatch.
    """

    def __init__(
        self,
        runtime: "RuntimeProtocol",
        task_registry: "TaskRegistryProtocol",
        runtime_builder: "RuntimeBuilderProtocol",
        prompt_builder: "PromptBuilderProtocol",
    ) -> None:
        self.runtime = runtime
        self.task_registry = task_registry
        self.runtime_builder = runtime_builder
        self.prompt_builder = prompt_builder

        # Bookkeeping across the lifetime of one Harbor Job:
        self._current_env: str | None = None
        self._eval_outcomes_buffer: list = []
        self._pre_state_cache: dict[str, dict] = {}
        # Count of LEARNING-role trials completed per env. Used to detect
        # the last learning trial of an env (which is the right moment to
        # freeze, BEFORE the first eval trial's container is constructed).
        # See _on_trial_ended_sync's freeze trigger.
        self._learning_completed_per_env: dict[str, int] = {}
        # Evaluation-only curated diagnostics skip T1, so all five gold
        # family skills are seeded together before the first T4 starts.
        self._oracle_seeded_envs: set[str] = set()
        # Same-session candidates are generated before Harbor stops the task
        # environment, then consumed by the ordinary END hook. Keying mirrors
        # _pre_state_cache so shadow/replay names cannot alias a primary trial.
        self._reflection_cache: dict[str, ReflectionRecord] = {}

    # ==================================================================
    # HOOK 1: on_trial_started
    # ==================================================================

    async def on_trial_started(self, event: "TrialHookEvent") -> None:
        """Pre-trial: curated/zero-shot seed, freeze trigger, retrieval, build."""
        task = self._resolve_task(event)
        runtime_basename = self._runtime_basename(event)
        is_shadow = _is_shadow_trial_name(runtime_basename)

        # Shadow trials are dual-T6 second runs. They short-circuit ALL
        # mutating logic (curated inject / zero-shot create / env
        # transition / freeze) -- the primary trial that ran microseconds
        # earlier already did all of that, the library is frozen, and the
        # only thing the shadow needs is a fresh OracleRetriever-based
        # instruction.md targeted at its own runtime dir.
        if is_shadow:
            await self._on_shadow_trial_started(event, task, runtime_basename)
            return

        # Detect within-env replay trial. Replays share a TaskSpec with
        # an original (same family, same role, same task content) but
        # run AFTER the env's 30 originals have completed -- library is
        # at its post-evolution state and must stay frozen for the
        # replay's duration. We branch BEFORE env-transition logic so
        # replays don't accidentally trigger unfreeze/maintain.
        is_replay = _is_replay_trial_name(runtime_basename)

        # ---- 1. Env transition: unfreeze previous env + maintain ----
        # MUST run before steps 2-3 (Path-A/B writes to library): on the
        # first task of a new env, the previous env's eval block left the
        # library frozen, so any inject_curated / create_skill call here
        # would raise PermissionError("... called while frozen") and crash
        # the run. Unfreezing first lets the new env's canonical task
        # mutate the library legally.
        # Replay trials never trigger env transition: by construction
        # they're scheduled AFTER the env's 30 originals, so the env_id
        # hasn't changed (unfreeze would let mutation back in, the very
        # thing replay is meant to forbid).
        if (
            not is_replay
            and self._current_env is not None
            and task.environment_id != self._current_env
        ):
            await self._handle_env_transition(self._current_env, task.environment_id)
        self._current_env = task.environment_id

        # ---- 1b. Per-env library swap (library_scope=="environment") ----
        # Lazy-init this env's LibraryStore (own git repo + manifest) on
        # first encounter; subsequent calls within the same env are cheap
        # dict lookups. Also rebuilds freeze_ctrl + snapshot_store so they
        # point at the current env's library. No-op for library_scope=
        # "global" (single library wired at runtime build time).
        # MUST run BEFORE inject_curated / zero_shot_create / freeze
        # below -- they access ``runtime.library`` and need the right
        # env's LibraryStore.
        self.runtime.switch_env(task.environment_id)

        # The matched T4-T6 oracle diagnostic deliberately has no learning
        # trials. Seed the complete curated environment library once before
        # freezing it; the per-trial oracle view below will expose only the
        # annotated relevant subset to the task agent.
        if (
            self.runtime.run_config.evaluation_only_t4_t6
            and self.runtime.baseline.allow_curated_inject
        ):
            self._seed_curated_environment(task.environment_id, task.task_id)

        # ---- 2. Path-B curated injection (on first arrival of family) ----
        # SKIPPED for replays: curated v0 was already injected during the
        # original T1 of this family; replay must observe the post-
        # evolution library, not re-inject v0.
        if (
            not is_replay
            and self.runtime.baseline.allow_curated_inject
            and task.role == TaskRole.CANONICAL.value
            and not self.runtime.library.has_curated_for(task.family_id)
        ):
            self._inject_curated_v0(task)

        # ---- 3. Self-Gen-Zero-Shot creation (before any execution) ----
        # SKIPPED for replays (same rationale as step 2).
        if (
            not is_replay
            and self.runtime.baseline.allow_zero_shot_creation
            and task.role == TaskRole.CANONICAL.value
            and not self.runtime.library.has_seed_for(task.family_id)
        ):
            await self._create_zero_shot_skill(task)

        # ---- 4. Freeze trigger fallback: idempotent if T3 trial_ended
        # already wrote the marker (the canonical place; see
        # _on_trial_ended_sync). We keep this T4-START fallback so a
        # missed T3 ended (e.g., orphan_trial_ended) still flips into
        # the eval block.
        # SKIPPED for replays: library is already frozen (replays only
        # ever run after the eval block, so freeze marker was set by T4
        # of this env's original phase). Re-asserting freeze here is
        # idempotent but the explicit skip makes intent clear.
        if (
            not is_replay
            and task.role == TaskRole.CONTEXT_SHIFT.value
            and not self.runtime.freeze_ctrl.frozen
        ):
            self.runtime.freeze_ctrl.freeze(task.environment_id)

        # ---- 5. Skill retrieval (if baseline uses skill library) ----
        retrieval = None
        if (
            self.runtime.baseline.use_skill_library
            and not self.runtime.run_config.shuffled_skill_view
        ):
            instruction_text = self._read_instruction(task)
            retrieval = self.runtime.retriever.retrieve(
                query=instruction_text,
                library=self.runtime.library,
                k=self.runtime.baseline.skill_retrieval_k,
            )
            if hasattr(self.runtime, "retrieval_store"):
                self.runtime.retrieval_store.record(
                    task_id=task.task_id,
                    retrieval=retrieval,
                    required_skills=task.required_skills,
                )

        # ---- 6. Trajectory / history retrieval (control baselines) ----
        trajectories: list = []
        if (
            self.runtime.baseline.use_trajectory_rag
            and self.runtime.trajectory_retriever
        ):
            trajectories = self.runtime.trajectory_retriever.retrieve(
                task=task,
                k=self.runtime.baseline.trajectory_retrieval_k,
            )
        history_context: str | None = None
        if self.runtime.baseline.use_history_context and self.runtime.history_retriever:
            history_context = self.runtime.history_retriever.build_context(
                task=task,
                max_tokens=self.runtime.baseline.history_context_max_tokens,
            )

        if self.runtime.run_config.oracle_skill_view:
            self._stage_oracle_skill_view(task, runtime_basename)
        elif self.runtime.run_config.shuffled_skill_view:
            self._stage_shuffled_skill_view(task, runtime_basename)

        # ---- 7. Build runtime task copy (overwrites instruction.md) ----
        # Pass runtime_basename so replay/shadow trials write to their own
        # __replay / __oracle_shadow runtime dir (NOT the bare task_id dir,
        # which would clobber the original trial's instruction.md and leave
        # the replay agent reading an un-injected bare task instruction).
        runtime_task_dir = self.runtime_builder.build(
            task=task,
            run_root=self.runtime.run_root,
            baseline=self.runtime.baseline,
            retrieved_skills=(retrieval.skills if retrieval else []),
            retrieved_trajectories=trajectories,
            history_context=history_context,
            library_frozen=self.runtime.freeze_ctrl.frozen,
            runtime_basename=runtime_basename,
        )

        # ---- 8. Cache pre-state for on_trial_ended ----
        cache_key = runtime_basename if (is_shadow or is_replay) else task.task_id
        self._pre_state_cache[cache_key] = {
            "library_hash": self.runtime.library.compute_hash(),
            "retrieval": retrieval,
            "runtime_dir": runtime_task_dir,
            "started_at": datetime.now(timezone.utc),
        }

        self.runtime.event_store.record(
            "trial_started",
            {
                "task_id": task.task_id,
                "role": task.role,
                "phase": task.phase,
                "library_hash": self.runtime.library.compute_hash(),
                "retrieved_skill_ids": (
                    [s.skill_id for s in retrieval.skills] if retrieval else []
                ),
            },
        )

    # ==================================================================
    # POST-VERIFIER SEAM (before Harbor stops the shared environment)
    # ==================================================================

    async def on_post_verifier_repair(self, trial: Any, failed_attempt: int) -> bool:
        """Run one bounded-feedback repair turn after a failed learning attempt.

        Return ``True`` only after the exact solve session has completed a
        repair turn and a new immutable /root/task snapshot is ready for a
        fresh isolated verifier. The Harbor compatibility seam owns the outer
        loop and calls this method after every verifier invocation.
        """

        if self.runtime.baseline.skill_update_source != "same_agent_session":
            return False

        event = SimpleNamespace(
            task_name=getattr(getattr(trial, "task", None), "name", ""),
            config=getattr(trial, "config", None),
            result=getattr(trial, "result", None),
        )
        task = self._resolve_task(event)
        runtime_basename = self._runtime_basename(event)
        if (
            _is_shadow_trial_name(runtime_basename)
            or _is_replay_trial_name(runtime_basename)
            or task.role in {r.value for r in _EVAL_ROLES}
        ):
            return False

        if failed_attempt < 1:
            raise UnscoreableTrialError(
                "repair-attempt-index-invalid", task_id=task.task_id
            )
        max_attempts = int(self.runtime.baseline.learning_max_attempts)
        outcome = self.runtime.verifier_adapter.parse(trial.result)
        if failed_attempt == 1:
            trial._sevb_initial_verifier_passed = bool(outcome.verifier_passed)
        trial._sevb_terminal_verifier_passed = bool(outcome.verifier_passed)
        trial._sevb_learning_attempt_count = failed_attempt

        if bool(outcome.verifier_passed) or failed_attempt >= max_attempts:
            self.runtime.event_store.record(
                "same_session_attempt_terminal",
                {
                    "task_id": task.task_id,
                    "learning_attempts": failed_attempt,
                    "verifier_passed": bool(outcome.verifier_passed),
                    "max_attempts": max_attempts,
                },
            )
            return False

        if getattr(trial, "_is_agent_environment_stopped", False):
            raise UnscoreableTrialError(
                "repair-environment-already-stopped", task_id=task.task_id
            )
        if not getattr(trial.agent_environment.capabilities, "mounted", False):
            raise UnscoreableTrialError(
                "repair-requires-mounted-agent-logs", task_id=task.task_id
            )
        if not getattr(trial, "_sevb_agent_main_stopped", False):
            raise UnscoreableTrialError(
                "repair-requires-stopped-container", task_id=task.task_id
            )

        agent_dir = Path(trial.paths.agent_dir)
        canonical_trajectory = agent_dir / "trajectory.json"
        agent_name = self.runtime.baseline.harbor_agent_name
        session_export = agent_dir / "opencode.session.json"
        repair_stream = agent_dir / (
            "codex.txt" if agent_name == "codex" else "opencode.reflection.jsonl"
        )
        task_snapshot = Path(trial.paths.artifacts_dir) / "root" / "task"

        audit_root = Path(trial.paths.trial_dir) / REPAIR_AUDIT_DIRNAME
        if failed_attempt == 1:
            if os.path.lexists(audit_root):
                raise UnscoreableTrialError(
                    "repair-audit-dir-preexists", task_id=task.task_id
                )
            audit_root.mkdir(mode=0o700)
        elif not audit_root.is_dir() or audit_root.is_symlink():
            raise UnscoreableTrialError(
                "repair-audit-dir-missing", task_id=task.task_id
            )
        attempt_dir = audit_root / f"attempt-{failed_attempt:02d}"
        if os.path.lexists(attempt_dir):
            raise UnscoreableTrialError(
                "repair-attempt-audit-preexists", task_id=task.task_id
            )
        attempt_dir.mkdir(mode=0o700)

        repair = InSessionSkillReflection(
            baseline=self.runtime.baseline,
            library=self.runtime.library,
        )
        prompt, feedback = repair.build_repair_prompt(
            task,
            outcome,
            failed_attempt=failed_attempt,
            max_attempts=max_attempts,
        )
        self._write_new_regular(
            attempt_dir / "repair_prompt.md", prompt.encode("utf-8"), task.task_id
        )
        self._write_new_regular(
            attempt_dir / "repair_feedback.json",
            (json.dumps(feedback, indent=2, ensure_ascii=False) + "\n").encode(),
            task.task_id,
        )
        self._write_new_regular(
            attempt_dir / "outcome.json",
            (
                json.dumps(
                    {
                        "attempt": failed_attempt,
                        "verifier_passed": bool(outcome.verifier_passed),
                        "reward": float(outcome.reward),
                    },
                    indent=2,
                )
                + "\n"
            ).encode(),
            task.task_id,
        )

        await self._require_main_not_running(trial, task_id=task.task_id)
        prefix_trajectory, prefix_trajectory_raw = self._capture_agent_file(
            canonical_trajectory,
            attempt_dir / "trajectory.before-repair.json",
            task_id=task.task_id,
            reason="repair-missing-prefix-trajectory",
        )
        if agent_name == "codex":
            prefix_export, prefix_export_raw, prefix_export_session_id = (
                self._capture_codex_session(
                    agent_dir,
                    attempt_dir / "codex.session.before-repair.jsonl",
                    task_id=task.task_id,
                    reason="repair-missing-prefix-session-export",
                )
            )
        else:
            prefix_export, prefix_export_raw = self._capture_agent_file(
                session_export,
                attempt_dir / "opencode.session.before-repair.json",
                task_id=task.task_id,
                reason="repair-missing-prefix-session-export",
            )
            prefix_export_payload = self._json_object(
                prefix_export_raw,
                reason="repair-prefix-session-export-invalid",
                task_id=task.task_id,
            )
            prefix_export_session_id = self._session_id_from_export(
                prefix_export_payload, task_id=task.task_id
            )
        prefix_payload = self._json_object(
            prefix_trajectory_raw,
            reason="repair-prefix-trajectory-invalid",
            task_id=task.task_id,
        )
        prefix_session_id = self._session_id_from_trajectory(
            prefix_payload, task_id=task.task_id
        )
        adapter_session_id = (
            prefix_session_id
            if agent_name == "codex"
            else getattr(trial.agent, "opencode_session_id", None)
        )
        if not (
            isinstance(adapter_session_id, str)
            and adapter_session_id
            and adapter_session_id == prefix_session_id == prefix_export_session_id
        ):
            raise UnscoreableTrialError(
                "repair-prefix-session-mismatch", task_id=task.task_id
            )

        self._copy_task_tree_nofollow(
            task_snapshot,
            attempt_dir / "task.before-repair",
            task_id=task.task_id,
        )
        task_hash_before = self._hash_tree_nofollow(task_snapshot, task_id=task.task_id)
        verifier_snapshot = attempt_dir / "official-verifier"
        self._copy_tree_nofollow(
            Path(trial.paths.verifier_dir),
            verifier_snapshot,
            task_id=task.task_id,
        )
        self._empty_directory(Path(trial.paths.verifier_dir))

        main_stopped_proven = True
        pending_error: BaseException | None = None
        try:
            main_stopped_proven = False
            await self._restart_main_and_prove(trial, task_id=task.task_id)
            await trial.agent_environment.empty_dirs(
                [trial.agent_env_paths.tests_dir], chmod=False
            )
            target = SimpleNamespace(agent_result=None, agent_execution=None)
            phase_error: BaseException | None = None
            try:
                await trial._run_agent_phase(
                    target=target,
                    instruction=prompt,
                    timeout_sec=trial._agent_timeout_sec,
                    user=trial.task.config.agent.user,
                    resume=True,
                )
            except BaseException as exc:
                phase_error = exc
            finally:
                await self._stop_main_and_prove(trial, task_id=task.task_id)
                main_stopped_proven = True
            if phase_error is not None:
                raise phase_error
            if target.agent_result is None:
                raise UnscoreableTrialError(
                    "repair-missing-agent-context", task_id=task.task_id
                )

            if agent_name != "codex":
                full_export_raw = self._read_regular_nofollow(
                    session_export,
                    max_bytes=_MAX_AUDIT_FILE_BYTES,
                    task_id=task.task_id,
                    reason="repair-full-session-export-invalid",
                )
                self._replace_with_regular(
                    session_export, full_export_raw, task_id=task.task_id
                )
            self._replace_with_regular(canonical_trajectory, b"", task_id=task.task_id)
            trial.agent.populate_context_post_run(target.agent_result)
            trial.result.agent_result = target.agent_result

            _, full_trajectory_raw = self._capture_agent_file(
                canonical_trajectory,
                attempt_dir / "trajectory.after-repair.json",
                task_id=task.task_id,
                reason="repair-full-trajectory-invalid",
            )
            if agent_name == "codex":
                _, full_export_raw, full_export_session_id = (
                    self._capture_codex_session(
                        agent_dir,
                        attempt_dir / "codex.session.after-repair.jsonl",
                        task_id=task.task_id,
                        reason="repair-full-session-export-invalid",
                    )
                )
            else:
                self._write_new_regular(
                    attempt_dir / "opencode.session.after-repair.json",
                    full_export_raw,
                    task.task_id,
                )
            _, repair_stream_raw = self._capture_agent_file(
                repair_stream,
                attempt_dir
                / (
                    "codex.repair.jsonl"
                    if agent_name == "codex"
                    else "opencode.repair.jsonl"
                ),
                task_id=task.task_id,
                reason="repair-missing-stream",
            )
            full_payload = self._json_object(
                full_trajectory_raw,
                reason="repair-full-trajectory-invalid",
                task_id=task.task_id,
            )
            full_session_id = self._verify_trajectory_continuity(
                prefix_payload,
                full_payload,
                prompt=prompt,
                task_id=task.task_id,
            )
            if agent_name == "codex":
                full_export_session_id = self._verify_codex_session_continuity(
                    prefix_export_raw,
                    full_export_raw,
                    task_id=task.task_id,
                )
                repair_stream_session_id = full_export_session_id
                resumed_adapter_session_id = full_export_session_id
            else:
                full_export_payload = self._json_object(
                    full_export_raw,
                    reason="repair-full-session-export-invalid",
                    task_id=task.task_id,
                )
                full_export_session_id = self._verify_export_continuity(
                    prefix_export_payload,
                    full_export_payload,
                    prompt=prompt,
                    task_id=task.task_id,
                )
                repair_stream_session_id = self._session_id_from_stream(
                    repair_stream_raw,
                    task_id=task.task_id,
                    phase=f"repair-{failed_attempt}",
                )
                resumed_adapter_session_id = getattr(
                    trial.agent, "opencode_session_id", None
                )
            if not (
                adapter_session_id
                == resumed_adapter_session_id
                == full_session_id
                == full_export_session_id
                == repair_stream_session_id
            ):
                raise UnscoreableTrialError(
                    "repair-session-identity-mismatch", task_id=task.task_id
                )

            repaired_task = attempt_dir / "task.after-repair"
            repaired_task.mkdir(mode=0o700)
            await trial.agent_environment.service_download_dir(
                "/root/task", repaired_task, service="main"
            )
            task_hash_after = self._hash_tree_nofollow(
                repaired_task, task_id=task.task_id
            )
            if task_snapshot.is_symlink() or not task_snapshot.is_dir():
                raise UnscoreableTrialError(
                    "repair-task-snapshot-invalid", task_id=task.task_id
                )
            shutil.rmtree(task_snapshot)
            self._copy_task_tree_nofollow(
                repaired_task, task_snapshot, task_id=task.task_id
            )
            if (
                self._hash_tree_nofollow(task_snapshot, task_id=task.task_id)
                != task_hash_after
            ):
                raise UnscoreableTrialError(
                    "repair-task-snapshot-copy-mismatch", task_id=task.task_id
                )

            record = {
                "failed_attempt": failed_attempt,
                "next_attempt": failed_attempt + 1,
                "session_id": adapter_session_id,
                "same_session_verified": True,
                "task_hash_before": task_hash_before,
                "task_hash_after": task_hash_after,
                "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest(),
            }
            self._write_new_regular(
                attempt_dir / "repair_result.json",
                (json.dumps(record, indent=2) + "\n").encode(),
                task.task_id,
            )
            trial._sevb_repair_records = [
                *list(getattr(trial, "_sevb_repair_records", [])),
                record,
            ]
            self.runtime.event_store.record(
                "same_session_repair_completed",
                {
                    "task_id": task.task_id,
                    **record,
                },
            )
        except BaseException as exc:
            pending_error = exc
        finally:
            if not main_stopped_proven:
                try:
                    await self._stop_main_and_prove(trial, task_id=task.task_id)
                except BaseException as exc:
                    pending_error = pending_error or exc

        if pending_error is not None:
            raise pending_error
        return True

    async def on_post_verifier(self, trial: Any) -> None:
        """Resume the original agent session for one reflection turn.

        This is called by the exact-version Harbor compatibility patch after
        ``SingleStepTrial._run_verifier`` returns. It intentionally runs before
        ``TrialEvent.END`` because END is emitted only after container stop.
        """
        if self.runtime.baseline.skill_update_source != "same_agent_session":
            return

        event = SimpleNamespace(
            task_name=getattr(getattr(trial, "task", None), "name", ""),
            config=getattr(trial, "config", None),
            result=getattr(trial, "result", None),
        )
        task = self._resolve_task(event)
        runtime_basename = self._runtime_basename(event)
        is_shadow = _is_shadow_trial_name(runtime_basename)
        is_replay = _is_replay_trial_name(runtime_basename)
        cache_key = runtime_basename if (is_shadow or is_replay) else task.task_id

        # Evaluation, replay, and oracle-shadow trials remain frozen observers.
        if is_shadow or is_replay or task.role in {r.value for r in _EVAL_ROLES}:
            return

        if getattr(trial, "_is_agent_environment_stopped", False):
            raise UnscoreableTrialError(
                "reflection-environment-already-stopped", task_id=task.task_id
            )
        if not getattr(trial.agent_environment.capabilities, "mounted", False):
            raise UnscoreableTrialError(
                "reflection-requires-mounted-agent-logs", task_id=task.task_id
            )
        if not getattr(trial, "_sevb_agent_main_stopped", False):
            raise UnscoreableTrialError(
                "reflection-requires-stopped-solve-container",
                task_id=task.task_id,
            )

        # Fail closed against missing/contradictory official verifier state
        # before the model sees any feedback or a library candidate is cached.
        outcome = self.runtime.verifier_adapter.parse(trial.result)
        learning_attempts = int(getattr(trial, "_sevb_learning_attempt_count", 1) or 1)
        repair_records = list(getattr(trial, "_sevb_repair_records", []))
        initial_verifier_passed = bool(
            getattr(
                trial,
                "_sevb_initial_verifier_passed",
                outcome.verifier_passed,
            )
        )
        terminal_verifier_passed = bool(outcome.verifier_passed)
        all_attempts_same_session_verified = len(repair_records) == max(
            0, learning_attempts - 1
        ) and all(
            item.get("same_session_verified") is True
            for item in repair_records
            if isinstance(item, dict)
        )
        attempt_audit_dir = Path(trial.paths.trial_dir) / REPAIR_AUDIT_DIRNAME
        if not attempt_audit_dir.is_dir() or attempt_audit_dir.is_symlink():
            attempt_audit_dir = None
        reflection = InSessionSkillReflection(
            baseline=self.runtime.baseline,
            # Always take the current runtime library: environment-scoped runs
            # swap LibraryStore objects as E1..E6 advance.
            library=self.runtime.library,
        )
        should_reflect, mode_or_reason = reflection.plan(task, outcome)
        if not should_reflect:
            record = ReflectionRecord(
                status="skipped",
                task_id=task.task_id,
                reason=mode_or_reason,
                learning_attempts=learning_attempts,
                repair_attempts=max(0, learning_attempts - 1),
                initial_verifier_passed=initial_verifier_passed,
                terminal_verifier_passed=terminal_verifier_passed,
                repaired_to_pass=(
                    not initial_verifier_passed and terminal_verifier_passed
                ),
                all_attempts_same_session_verified=(all_attempts_same_session_verified),
                attempt_audit_dir=attempt_audit_dir,
            )
            self._reflection_cache[cache_key] = record
            self.runtime.event_store.record("reflection_skipped", record.to_dict())
            return
        mode = mode_or_reason

        agent_dir = Path(trial.paths.agent_dir)
        agent_name = self.runtime.baseline.harbor_agent_name
        candidate_path = agent_dir / REFLECTION_CANDIDATE_FILENAME
        canonical_trajectory = agent_dir / "trajectory.json"
        session_export = agent_dir / "opencode.session.json"
        solve_stream = agent_dir / (
            "codex.txt" if agent_name == "codex" else "opencode.solve.jsonl"
        )
        reflection_stream = agent_dir / (
            "codex.txt" if agent_name == "codex" else "opencode.reflection.jsonl"
        )

        prompt, feedback = reflection.build_prompt(task, outcome, mode=mode)
        audit_dir = self._create_host_audit_dir(trial, task_id=task.task_id)
        prompt_path = audit_dir / REFLECTION_PROMPT_FILENAME
        feedback_path = audit_dir / REFLECTION_FEEDBACK_FILENAME
        result_path = audit_dir / REFLECTION_RESULT_FILENAME
        self._write_new_regular(prompt_path, prompt.encode("utf-8"), task.task_id)
        self._write_new_regular(
            feedback_path,
            (json.dumps(feedback, indent=2, ensure_ascii=False) + "\n").encode(),
            task.task_id,
        )

        # The solve container arrived stopped. Capture all model-controlled
        # inputs through no-follow file descriptors before it can run again.
        await self._require_main_not_running(trial, task_id=task.task_id)
        self._remove_agent_candidate(candidate_path, task_id=task.task_id)
        solve_trajectory, solve_trajectory_raw = self._capture_agent_file(
            canonical_trajectory,
            audit_dir / "trajectory.solve.json",
            task_id=task.task_id,
            reason="reflection-missing-solve-trajectory",
        )
        if agent_name == "codex":
            solve_export, solve_export_raw, solve_export_session_id = (
                self._capture_codex_session(
                    agent_dir,
                    audit_dir / "codex.session.solve.jsonl",
                    task_id=task.task_id,
                    reason="reflection-missing-solve-session-export",
                )
            )
        else:
            solve_export, solve_export_raw = self._capture_agent_file(
                session_export,
                audit_dir / "opencode.session.solve.json",
                task_id=task.task_id,
                reason="reflection-missing-solve-session-export",
            )
        self._capture_agent_file(
            solve_stream,
            audit_dir
            / (
                "codex.solve.jsonl" if agent_name == "codex" else "opencode.solve.jsonl"
            ),
            task_id=task.task_id,
            reason="reflection-missing-solve-stream",
        )
        solve_payload = self._json_object(
            solve_trajectory_raw,
            reason="reflection-solve-trajectory-invalid",
            task_id=task.task_id,
        )
        solve_session_id = self._session_id_from_trajectory(
            solve_payload, task_id=task.task_id
        )
        if agent_name == "codex":
            solve_stream_session_id = solve_export_session_id
            adapter_session_id = solve_session_id
        else:
            solve_export_payload = self._json_object(
                solve_export_raw,
                reason="reflection-solve-session-export-invalid",
                task_id=task.task_id,
            )
            solve_export_session_id = self._session_id_from_export(
                solve_export_payload, task_id=task.task_id
            )
            solve_stream_session_id = self._session_id_from_stream(
                self._read_regular_nofollow(
                    solve_stream,
                    max_bytes=_MAX_AUDIT_FILE_BYTES,
                    task_id=task.task_id,
                    reason="reflection-solve-stream-invalid",
                ),
                task_id=task.task_id,
                phase="solve",
            )
            adapter_session_id = getattr(trial.agent, "opencode_session_id", None)
        if not (
            isinstance(adapter_session_id, str)
            and adapter_session_id
            and adapter_session_id
            == solve_session_id
            == solve_export_session_id
            == solve_stream_session_id
        ):
            raise UnscoreableTrialError(
                "reflection-solve-session-mismatch", task_id=task.task_id
            )

        task_snapshot = Path(trial.paths.artifacts_dir) / "root" / "task"
        task_hash_before = self._hash_tree_nofollow(task_snapshot, task_id=task.task_id)
        official_verifier = self._snapshot_and_hide_verifier(
            trial, audit_dir=audit_dir, task_id=task.task_id
        )

        record: ReflectionRecord | None = None
        pending_error: BaseException | None = None
        main_stopped_proven = True
        reflection_timed_out = False
        reflection_stream_raw: bytes | None = None
        try:
            main_stopped_proven = False
            await self._restart_main_and_prove(trial, task_id=task.task_id)

            # Hidden tests ran only in the destroyed verifier container. Empty
            # /tests defensively; bounded feedback in the prompt is the only
            # authorized verifier signal.
            await trial.agent_environment.empty_dirs(
                [trial.agent_env_paths.tests_dir], chmod=False
            )

            target = SimpleNamespace(agent_result=None, agent_execution=None)
            phase_error: BaseException | None = None
            try:
                await trial._run_agent_phase(
                    target=target,
                    instruction=prompt,
                    timeout_sec=trial._agent_timeout_sec,
                    user=trial.task.config.agent.user,
                    resume=True,
                )
            except BaseException as exc:
                phase_error = exc
            finally:
                # Stop immediately when the resumed CLI returns (successfully or
                # otherwise), then prove no background process remains.
                await self._stop_main_and_prove(trial, task_id=task.task_id)
                main_stopped_proven = True
            if phase_error is not None:
                if not _is_agent_timeout_error(phase_error):
                    raise phase_error
                if agent_name == "codex":
                    # Harbor's Codex adapter copies its native session in a
                    # best-effort ``finally`` block. A cancelled turn cannot
                    # prove that copy is complete, so fail the trial closed
                    # and let only the outer clean-episode retry recover it.
                    raise phase_error

                # A reflection budget expiry is scoreable only when the
                # already-written stream and a bounded export of the exact
                # solve session provide the same evidence as a normal return.
                # Recovery invokes no model turn; the task's resolved agent
                # timeout remains the model-turn budget.
                reflection_timed_out = True
                _, reflection_stream_raw = self._capture_agent_file(
                    reflection_stream,
                    audit_dir / "opencode.reflection.jsonl",
                    task_id=task.task_id,
                    reason="reflection-missing-reflection-stream",
                )
                timed_out_stream_session_id = self._session_id_from_stream(
                    reflection_stream_raw,
                    task_id=task.task_id,
                    phase="reflection",
                )
                if timed_out_stream_session_id != adapter_session_id:
                    raise UnscoreableTrialError(
                        "reflection-session-identity-mismatch",
                        task_id=task.task_id,
                    )

                recover = getattr(trial.agent, "recover_timed_out_resume", None)
                if not callable(recover):
                    raise UnscoreableTrialError(
                        "reflection-timeout-recovery-unsupported",
                        task_id=task.task_id,
                    )

                main_stopped_proven = False
                await self._restart_main_and_prove(trial, task_id=task.task_id)
                default_user_scope = getattr(
                    trial.agent_environment, "with_default_user", None
                )
                exec_env_scope = getattr(
                    trial.agent_environment, "scoped_exec_env", None
                )
                if not callable(default_user_scope) or not callable(exec_env_scope):
                    raise UnscoreableTrialError(
                        "reflection-timeout-recovery-scope-unsupported",
                        task_id=task.task_id,
                    )
                try:
                    try:
                        with (
                            default_user_scope(trial.task.config.agent.user),
                            exec_env_scope(trial.agent.extra_env),
                        ):
                            recovered_session_id = await recover(
                                trial.agent_environment,
                                timeout_sec=_REFLECTION_EXPORT_TIMEOUT_SEC,
                            )
                    except Exception as exc:
                        raise UnscoreableTrialError(
                            "reflection-timeout-recovery-failed",
                            task_id=task.task_id,
                            exception_type=type(exc).__name__,
                        ) from exc
                finally:
                    await self._stop_main_and_prove(trial, task_id=task.task_id)
                    main_stopped_proven = True
                if recovered_session_id != adapter_session_id:
                    raise UnscoreableTrialError(
                        "reflection-session-identity-mismatch",
                        task_id=task.task_id,
                    )

            if agent_name != "codex":
                full_export_raw = self._read_regular_nofollow(
                    session_export,
                    max_bytes=_MAX_AUDIT_FILE_BYTES,
                    task_id=task.task_id,
                    reason="reflection-full-session-export-invalid",
                )
                # OpenCode's host-side converter consumes this export. Normalize
                # it before parsing so it cannot follow an agent-created link.
                self._replace_with_regular(
                    session_export, full_export_raw, task_id=task.task_id
                )
            if not reflection_timed_out:
                self._replace_with_regular(
                    canonical_trajectory, b"", task_id=task.task_id
                )
                if target.agent_result is None:
                    raise UnscoreableTrialError(
                        "reflection-missing-agent-context",
                        task_id=task.task_id,
                    )
                trial.agent.populate_context_post_run(target.agent_result)
                trial.result.agent_result = target.agent_result

            full_trajectory, full_trajectory_raw = self._capture_agent_file(
                canonical_trajectory,
                audit_dir / "trajectory.full.json",
                task_id=task.task_id,
                reason="reflection-full-trajectory-invalid",
            )
            if agent_name == "codex":
                full_export, full_export_raw, full_export_session_id = (
                    self._capture_codex_session(
                        agent_dir,
                        audit_dir / "codex.session.full.jsonl",
                        task_id=task.task_id,
                        reason="reflection-full-session-export-invalid",
                    )
                )
            else:
                full_export = audit_dir / "opencode.session.full.json"
                self._write_new_regular(full_export, full_export_raw, task.task_id)
            if reflection_stream_raw is None:
                _, reflection_stream_raw = self._capture_agent_file(
                    reflection_stream,
                    audit_dir
                    / (
                        "codex.reflection.jsonl"
                        if agent_name == "codex"
                        else "opencode.reflection.jsonl"
                    ),
                    task_id=task.task_id,
                    reason="reflection-missing-reflection-stream",
                )

            full_payload = self._json_object(
                full_trajectory_raw,
                reason="reflection-full-trajectory-invalid",
                task_id=task.task_id,
            )
            full_session_id = self._verify_trajectory_continuity(
                solve_payload,
                full_payload,
                prompt=prompt,
                task_id=task.task_id,
            )
            if agent_name == "codex":
                full_export_session_id = self._verify_codex_session_continuity(
                    solve_export_raw,
                    full_export_raw,
                    task_id=task.task_id,
                )
                reflection_stream_session_id = full_export_session_id
                reflection_session_id = full_export_session_id
            else:
                full_export_payload = self._json_object(
                    full_export_raw,
                    reason="reflection-full-session-export-invalid",
                    task_id=task.task_id,
                )
                full_export_session_id = self._verify_export_continuity(
                    solve_export_payload,
                    full_export_payload,
                    prompt=prompt,
                    task_id=task.task_id,
                )
                reflection_stream_session_id = self._session_id_from_stream(
                    reflection_stream_raw,
                    task_id=task.task_id,
                    phase="reflection",
                )
                reflection_session_id = getattr(
                    trial.agent, "opencode_session_id", None
                )
            if not (
                isinstance(reflection_session_id, str)
                and reflection_session_id
                and adapter_session_id
                == reflection_session_id
                == full_session_id
                == full_export_session_id
                == reflection_stream_session_id
            ):
                raise UnscoreableTrialError(
                    "reflection-session-identity-mismatch", task_id=task.task_id
                )

            reflection_task = audit_dir / "task.after"
            reflection_task.mkdir(mode=0o700)
            await trial.agent_environment.service_download_dir(
                "/root/task", reflection_task, service="main"
            )
            task_hash_after = self._hash_tree_nofollow(
                reflection_task, task_id=task.task_id
            )
            if task_hash_after != task_hash_before:
                raise UnscoreableTrialError(
                    "reflection-mutated-task-workspace", task_id=task.task_id
                )

            if reflection_timed_out:
                # A candidate left by a cancelled process did not finish within
                # the declared model-turn budget and must never mutate skills.
                record = ReflectionRecord(
                    status="rejected",
                    task_id=task.task_id,
                    mode=mode,
                    session_id=reflection_session_id,
                    solve_session_id=solve_session_id,
                    reflection_session_id=reflection_session_id,
                    same_session_verified=True,
                    reason=REFLECTION_AGENT_TIMEOUT_REASON,
                )
            else:
                candidate_raw: bytes | None = None
                candidate_audit_path: Path | None = None
                try:
                    candidate_raw = self._read_candidate_nofollow(candidate_path)
                    patch = reflection.parse_candidate_bytes(
                        candidate_raw,
                        task=task,
                        outcome=outcome,
                        mode=mode,
                    )
                except ReflectionCandidateError as exc:
                    record = ReflectionRecord(
                        status="rejected",
                        task_id=task.task_id,
                        mode=mode,
                        session_id=reflection_session_id,
                        solve_session_id=solve_session_id,
                        reflection_session_id=reflection_session_id,
                        same_session_verified=True,
                        reason=str(exc)[:300],
                    )
                else:
                    candidate_audit_path = audit_dir / REFLECTION_CANDIDATE_FILENAME
                    self._write_new_regular(
                        candidate_audit_path, candidate_raw, task.task_id
                    )
                    status = "noop" if patch is None else "completed"
                    record = ReflectionRecord(
                        status=status,
                        task_id=task.task_id,
                        mode=mode,
                        session_id=reflection_session_id,
                        solve_session_id=solve_session_id,
                        reflection_session_id=reflection_session_id,
                        same_session_verified=True,
                        patch=patch,
                        reason=("model_selected_noop" if patch is None else ""),
                        candidate_path=candidate_audit_path,
                    )

            assert record is not None
            record.prompt_path = prompt_path
            record.feedback_path = feedback_path
            record.solve_trajectory_path = solve_trajectory
            record.full_session_trajectory_path = full_trajectory
            record.solve_session_export_path = solve_export
            record.full_session_export_path = full_export
            record.prompt_sha256 = hashlib.sha256(prompt.encode()).hexdigest()
            record.solve_trajectory_sha256 = hashlib.sha256(
                solve_trajectory_raw
            ).hexdigest()
            record.full_session_trajectory_sha256 = hashlib.sha256(
                full_trajectory_raw
            ).hexdigest()
            record.solve_session_export_sha256 = hashlib.sha256(
                solve_export_raw
            ).hexdigest()
            record.full_session_export_sha256 = hashlib.sha256(
                full_export_raw
            ).hexdigest()
            record.task_workspace_hash_before = task_hash_before
            record.task_workspace_hash_after = task_hash_after
            record.trajectory_prefix_verified = True
            record.export_prefix_verified = True
        except BaseException as exc:
            pending_error = exc
        finally:
            # Even a failed resume must not expose verifier evidence until the
            # main service is independently proven stopped.
            if not main_stopped_proven:
                try:
                    await self._stop_main_and_prove(trial, task_id=task.task_id)
                    main_stopped_proven = True
                except BaseException as exc:
                    pending_error = pending_error or exc
            try:
                await trial._stop_agent_environment()
            except BaseException as exc:
                pending_error = pending_error or exc
            try:
                await self._require_main_not_running(trial, task_id=task.task_id)
                main_stopped_proven = True
            except BaseException as exc:
                main_stopped_proven = False
                pending_error = pending_error or exc
            if main_stopped_proven:
                try:
                    # Never leave a model-authored candidate in mounted logs.
                    # Timeout and recovery failures must not leak raw output.
                    self._remove_agent_candidate(candidate_path, task_id=task.task_id)
                except BaseException as exc:
                    pending_error = pending_error or exc
                try:
                    self._restore_verifier_evidence(
                        trial,
                        official_verifier=official_verifier,
                        audit_dir=audit_dir,
                        task_id=task.task_id,
                    )
                except BaseException as exc:
                    pending_error = pending_error or exc

        if pending_error is not None:
            raise pending_error
        assert record is not None
        record.learning_attempts = learning_attempts
        record.repair_attempts = max(0, learning_attempts - 1)
        record.initial_verifier_passed = initial_verifier_passed
        record.terminal_verifier_passed = terminal_verifier_passed
        record.repaired_to_pass = (
            not initial_verifier_passed and terminal_verifier_passed
        )
        record.all_attempts_same_session_verified = all_attempts_same_session_verified
        record.attempt_audit_dir = attempt_audit_dir
        self._write_new_regular(
            result_path,
            (
                json.dumps(record.to_dict(), indent=2, ensure_ascii=False) + "\n"
            ).encode(),
            task.task_id,
        )
        self._reflection_cache[cache_key] = record
        self.runtime.event_store.record(f"reflection_{record.status}", record.to_dict())

    @staticmethod
    def _create_host_audit_dir(trial: Any, *, task_id: str) -> Path:
        audit_dir = Path(trial.paths.trial_dir) / _AUDIT_DIRNAME
        if os.path.lexists(audit_dir):
            raise UnscoreableTrialError(
                "reflection-audit-dir-preexists", task_id=task_id
            )
        try:
            audit_dir.mkdir(mode=0o700)
        except OSError as exc:
            raise UnscoreableTrialError(
                "reflection-audit-dir-create-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc
        return audit_dir

    @staticmethod
    def _read_regular_nofollow(
        path: Path,
        *,
        max_bytes: int,
        task_id: str,
        reason: str,
    ) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except OSError as exc:
            raise UnscoreableTrialError(
                reason, task_id=task_id, exception_type=type(exc).__name__
            ) from exc
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode) or metadata.st_size > max_bytes:
                raise UnscoreableTrialError(reason, task_id=task_id)
            chunks: list[bytes] = []
            remaining = max_bytes + 1
            while remaining:
                chunk = os.read(fd, min(1024 * 1024, remaining))
                if not chunk:
                    break
                chunks.append(chunk)
                remaining -= len(chunk)
            raw = b"".join(chunks)
            if len(raw) > max_bytes:
                raise UnscoreableTrialError(reason, task_id=task_id)
            return raw
        finally:
            os.close(fd)

    @staticmethod
    def _write_new_regular(path: Path, raw: bytes, task_id: str) -> None:
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags, 0o600)
            try:
                view = memoryview(raw)
                while view:
                    written = os.write(fd, view)
                    view = view[written:]
            finally:
                os.close(fd)
        except OSError as exc:
            raise UnscoreableTrialError(
                "reflection-audit-write-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc

    @classmethod
    def _replace_with_regular(cls, path: Path, raw: bytes, *, task_id: str) -> None:
        try:
            path.unlink(missing_ok=True)
        except OSError as exc:
            raise UnscoreableTrialError(
                "reflection-agent-file-normalize-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc
        cls._write_new_regular(path, raw, task_id)

    @staticmethod
    def _remove_agent_candidate(path: Path, *, task_id: str) -> None:
        """Remove a stopped agent's candidate without following symlinks."""

        try:
            metadata = os.lstat(path)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise UnscoreableTrialError(
                "reflection-candidate-cleanup-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc
        try:
            if stat.S_ISDIR(metadata.st_mode) and not stat.S_ISLNK(metadata.st_mode):
                shutil.rmtree(path)
            else:
                os.unlink(path)
        except OSError as exc:
            raise UnscoreableTrialError(
                "reflection-candidate-cleanup-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc
        if os.path.lexists(path):
            raise UnscoreableTrialError(
                "reflection-candidate-cleanup-failed", task_id=task_id
            )

    @classmethod
    def _capture_agent_file(
        cls,
        source: Path,
        destination: Path,
        *,
        task_id: str,
        reason: str,
    ) -> tuple[Path, bytes]:
        raw = cls._read_regular_nofollow(
            source,
            max_bytes=_MAX_AUDIT_FILE_BYTES,
            task_id=task_id,
            reason=reason,
        )
        cls._write_new_regular(destination, raw, task_id)
        return destination, raw

    @staticmethod
    def _read_candidate_nofollow(path: Path) -> bytes:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
        try:
            fd = os.open(path, flags)
        except FileNotFoundError as exc:
            raise ReflectionCandidateError("candidate_file_missing") from exc
        except OSError as exc:
            raise ReflectionCandidateError("candidate_file_not_regular") from exc
        try:
            metadata = os.fstat(fd)
            if not stat.S_ISREG(metadata.st_mode):
                raise ReflectionCandidateError("candidate_file_not_regular")
            if metadata.st_size > _MAX_CANDIDATE_BYTES:
                raise ReflectionCandidateError("candidate_file_too_large")
            raw = os.read(fd, _MAX_CANDIDATE_BYTES + 1)
            if len(raw) > _MAX_CANDIDATE_BYTES:
                raise ReflectionCandidateError("candidate_file_too_large")
            return raw
        finally:
            os.close(fd)

    @staticmethod
    def _json_object(raw: bytes, *, reason: str, task_id: str) -> dict[str, Any]:
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise UnscoreableTrialError(reason, task_id=task_id) from exc
        if not isinstance(payload, dict):
            raise UnscoreableTrialError(reason, task_id=task_id)
        return payload

    @staticmethod
    def _session_id_from_trajectory(payload: dict[str, Any], *, task_id: str) -> str:
        session_id = payload.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            raise UnscoreableTrialError(
                "reflection-trajectory-missing-session", task_id=task_id
            )
        return session_id

    @staticmethod
    def _session_id_from_export(payload: dict[str, Any], *, task_id: str) -> str:
        info = payload.get("info")
        session_id = info.get("id") if isinstance(info, dict) else None
        if not isinstance(session_id, str) or not session_id:
            raise UnscoreableTrialError(
                "reflection-export-missing-session", task_id=task_id
            )
        return session_id

    @classmethod
    def _session_id_from_stream(cls, raw: bytes, *, task_id: str, phase: str) -> str:
        session_ids: set[str] = set()
        for line in raw.decode("utf-8", errors="replace").splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if isinstance(event, dict) and isinstance(event.get("sessionID"), str):
                session_ids.add(event["sessionID"])
        if len(session_ids) != 1:
            raise UnscoreableTrialError(
                f"reflection-{phase}-stream-session-invalid", task_id=task_id
            )
        return next(iter(session_ids))

    @classmethod
    def _capture_codex_session(
        cls,
        agent_dir: Path,
        destination: Path,
        *,
        task_id: str,
        reason: str,
    ) -> tuple[Path, bytes, str]:
        """Capture the one native Codex session JSONL without following links."""

        sessions_root = agent_dir / "sessions"
        if not sessions_root.is_dir() or sessions_root.is_symlink():
            raise UnscoreableTrialError(reason, task_id=task_id)

        session_files: list[Path] = []
        for root, dirnames, filenames in os.walk(sessions_root, followlinks=False):
            root_path = Path(root)
            for dirname in tuple(dirnames):
                child = root_path / dirname
                if child.is_symlink():
                    raise UnscoreableTrialError(reason, task_id=task_id)
            for filename in filenames:
                child = root_path / filename
                if child.is_symlink():
                    raise UnscoreableTrialError(reason, task_id=task_id)
                if child.suffix == ".jsonl":
                    session_files.append(child)

        if len(session_files) != 1:
            raise UnscoreableTrialError(reason, task_id=task_id)
        raw = cls._read_regular_nofollow(
            session_files[0],
            max_bytes=_MAX_AUDIT_FILE_BYTES,
            task_id=task_id,
            reason=reason,
        )
        session_id = cls._session_id_from_codex_session(raw, task_id=task_id)
        cls._write_new_regular(destination, raw, task_id)
        return destination, raw, session_id

    @staticmethod
    def _session_id_from_codex_session(raw: bytes, *, task_id: str) -> str:
        session_ids: set[str] = set()
        try:
            lines = raw.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise UnscoreableTrialError(
                "reflection-codex-session-invalid", task_id=task_id
            ) from exc
        for line in lines:
            if not line.strip():
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise UnscoreableTrialError(
                    "reflection-codex-session-invalid", task_id=task_id
                ) from exc
            if not isinstance(event, dict):
                raise UnscoreableTrialError(
                    "reflection-codex-session-invalid", task_id=task_id
                )
            if event.get("type") != "session_meta":
                continue
            payload = event.get("payload")
            session_id = payload.get("id") if isinstance(payload, dict) else None
            if isinstance(session_id, str) and session_id:
                session_ids.add(session_id)
        if len(session_ids) != 1:
            raise UnscoreableTrialError(
                "reflection-codex-session-missing-id", task_id=task_id
            )
        return next(iter(session_ids))

    @classmethod
    def _verify_codex_session_continuity(
        cls,
        solve_raw: bytes,
        full_raw: bytes,
        *,
        task_id: str,
    ) -> str:
        solve_id = cls._session_id_from_codex_session(solve_raw, task_id=task_id)
        full_id = cls._session_id_from_codex_session(full_raw, task_id=task_id)
        if solve_id != full_id or not full_raw.startswith(solve_raw):
            raise UnscoreableTrialError(
                "reflection-codex-session-prefix-mismatch", task_id=task_id
            )
        if len(full_raw) <= len(solve_raw):
            raise UnscoreableTrialError(
                "reflection-codex-session-tail-missing", task_id=task_id
            )
        return full_id

    @staticmethod
    def _opencode_exported_prompt_matches(message: str, prompt: str) -> bool:
        """Match the exact prompt or OpenCode 1.18.3's argv representation.

        The pinned CLI exports positional user prompts wrapped in double
        quotes with embedded double quotes backslash-escaped, while leaving
        newlines literal. Keep this an exact two-value allowlist: continuity
        must never degrade into whitespace or substring matching.
        """

        cli_rendered = '"' + prompt.replace('"', r"\"") + '"'
        return message == prompt or message == cli_rendered

    @staticmethod
    def _reflection_tail_state_machine(
        tail: list[Any],
        *,
        is_prompt: Callable[[Any], bool],
        is_regular_assistant: Callable[[Any], bool],
        is_compaction_sequence: Callable[[Any, Any, Any], bool],
        is_post_compaction_assistant: Callable[[Any, Any], bool],
    ) -> bool:
        """Validate one reflection turn with pinned auto-compaction interludes.

        OpenCode 1.18.3 can append a three-message control sequence while a
        turn is running: an auto-compaction user marker, an assistant summary,
        and one fixed synthetic user continuation.  The model must then return
        to an ordinary assistant message.  No other extra user message is
        accepted, and consecutive or incomplete compactions fail closed.
        """

        if not tail or not is_prompt(tail[0]):
            return False

        index = 1
        saw_regular_assistant = False
        while index < len(tail):
            item = tail[index]
            if is_regular_assistant(item):
                saw_regular_assistant = True
                index += 1
                continue

            if index + 3 >= len(tail):
                return False
            summary = tail[index + 1]
            synthetic_continue = tail[index + 2]
            returned_assistant = tail[index + 3]
            if not is_compaction_sequence(item, summary, synthetic_continue):
                return False
            if not is_post_compaction_assistant(returned_assistant, synthetic_continue):
                return False

            saw_regular_assistant = True
            index += 4

        return saw_regular_assistant

    @staticmethod
    def _trajectory_event(step: Any) -> Any:
        return step.get(OPENCODE_EVENT_KEY) if isinstance(step, dict) else None

    @classmethod
    def _trajectory_tail_is_valid(cls, tail: list[Any], *, prompt: str) -> bool:
        def is_compaction_sequence(
            compaction: Any, summary: Any, synthetic_continue: Any
        ) -> bool:
            if not all(
                isinstance(item, dict)
                for item in (compaction, summary, synthetic_continue)
            ):
                return False
            compaction_event = cls._trajectory_event(compaction)
            summary_event = cls._trajectory_event(summary)
            continue_event = cls._trajectory_event(synthetic_continue)
            if not all(
                isinstance(event, dict)
                for event in (compaction_event, summary_event, continue_event)
            ):
                return False

            compaction_id = compaction_event.get("message_id")
            summary_id = summary_event.get("message_id")
            continue_id = continue_event.get("message_id")
            overflow = compaction_event.get("overflow")
            return bool(
                isinstance(compaction_id, str)
                and compaction_id
                and isinstance(summary_id, str)
                and summary_id
                and isinstance(continue_id, str)
                and continue_id
                and isinstance(overflow, bool)
                and compaction.get("source") == "user"
                and compaction.get("message") == ""
                and compaction_event
                == {
                    "kind": OPENCODE_AUTO_COMPACTION_KIND,
                    "auto": True,
                    "overflow": overflow,
                    "exclusive": True,
                    "message_id": compaction_id,
                    "part_message_id": compaction_id,
                }
                and summary.get("source") == "agent"
                and summary_event
                == {
                    "kind": OPENCODE_COMPACTION_SUMMARY_KIND,
                    "summary": True,
                    "mode": "compaction",
                    "agent": "compaction",
                    "message_id": summary_id,
                    "parent_id": compaction_id,
                }
                and synthetic_continue.get("source") == "user"
                and synthetic_continue.get("message")
                == opencode_synthetic_continue(overflow=overflow)
                and continue_event
                == {
                    "kind": OPENCODE_COMPACTION_CONTINUE_KIND,
                    "synthetic": True,
                    "metadata": {"compaction_continue": True},
                    "exclusive": True,
                    "message_id": continue_id,
                    "part_message_id": continue_id,
                }
            )

        def is_post_compaction_assistant(
            assistant: Any, synthetic_continue: Any
        ) -> bool:
            if not isinstance(assistant, dict) or not isinstance(
                synthetic_continue, dict
            ):
                return False
            continue_event = cls._trajectory_event(synthetic_continue)
            assistant_event = cls._trajectory_event(assistant)
            if not isinstance(continue_event, dict) or not isinstance(
                assistant_event, dict
            ):
                return False
            continue_id = continue_event.get("message_id")
            return bool(
                isinstance(continue_id, str)
                and continue_id
                and assistant.get("source") == "agent"
                and assistant_event
                == {
                    "kind": OPENCODE_POST_COMPACTION_ASSISTANT_KIND,
                    "ordinary": True,
                    "continue_message_id": continue_id,
                    "parent_id": continue_id,
                }
            )

        return cls._reflection_tail_state_machine(
            tail,
            is_prompt=lambda step: (
                isinstance(step, dict)
                and step.get("source") == "user"
                and OPENCODE_EVENT_KEY not in step
                and isinstance(step.get("message"), str)
                and cls._opencode_exported_prompt_matches(step["message"], prompt)
            ),
            is_regular_assistant=lambda step: (
                isinstance(step, dict)
                and step.get("source") == "agent"
                and OPENCODE_EVENT_KEY not in step
            ),
            is_compaction_sequence=is_compaction_sequence,
            is_post_compaction_assistant=is_post_compaction_assistant,
        )

    @classmethod
    def _verify_trajectory_continuity(
        cls,
        solve: dict[str, Any],
        full: dict[str, Any],
        *,
        prompt: str,
        task_id: str,
    ) -> str:
        solve_id = cls._session_id_from_trajectory(solve, task_id=task_id)
        full_id = cls._session_id_from_trajectory(full, task_id=task_id)
        solve_steps = solve.get("steps")
        full_steps = full.get("steps")
        if (
            solve.get("schema_version") != full.get("schema_version")
            or solve_id != full_id
            or not isinstance(solve_steps, list)
            or not isinstance(full_steps, list)
            or full_steps[: len(solve_steps)] != solve_steps
        ):
            raise UnscoreableTrialError(
                "reflection-trajectory-prefix-mismatch", task_id=task_id
            )
        tail = full_steps[len(solve_steps) :]
        if not cls._trajectory_tail_is_valid(tail, prompt=prompt):
            raise UnscoreableTrialError(
                "reflection-trajectory-tail-invalid", task_id=task_id
            )
        return full_id

    @staticmethod
    def _export_message_text(message: dict[str, Any]) -> str:
        parts = message.get("parts")
        if not isinstance(parts, list):
            return ""
        return "\n".join(
            part["text"]
            for part in parts
            if isinstance(part, dict)
            and part.get("type") == "text"
            and isinstance(part.get("text"), str)
        )

    @staticmethod
    def _export_info(message: Any) -> dict[str, Any] | None:
        if not isinstance(message, dict):
            return None
        info = message.get("info")
        return info if isinstance(info, dict) else None

    @staticmethod
    def _export_parts(message: Any) -> list[Any] | None:
        if not isinstance(message, dict):
            return None
        parts = message.get("parts")
        return parts if isinstance(parts, list) else None

    @classmethod
    def _export_exact_user_text(
        cls,
        message: Any,
        *,
        matches: Callable[[str], bool],
    ) -> bool:
        info = cls._export_info(message)
        parts = cls._export_parts(message)
        return bool(
            info is not None
            and info.get("role") == "user"
            and "summary" not in info
            and parts is not None
            and len(parts) == 1
            and isinstance(parts[0], dict)
            and parts[0].get("type") == "text"
            and isinstance(parts[0].get("text"), str)
            and "synthetic" not in parts[0]
            and "metadata" not in parts[0]
            and matches(parts[0]["text"])
        )

    @classmethod
    def _export_regular_assistant(cls, message: Any) -> bool:
        info = cls._export_info(message)
        parts = cls._export_parts(message)
        return bool(
            info is not None
            and info.get("role") == "assistant"
            and "summary" not in info
            and parts is not None
            and all(
                isinstance(part, dict) and part.get("type") != "compaction"
                for part in parts
            )
        )

    @classmethod
    def _export_compaction_sequence(
        cls, compaction: Any, summary: Any, synthetic_continue: Any
    ) -> bool:
        compaction_info = cls._export_info(compaction)
        compaction_parts = cls._export_parts(compaction)
        summary_info = cls._export_info(summary)
        summary_parts = cls._export_parts(summary)
        continue_info = cls._export_info(synthetic_continue)
        continue_parts = cls._export_parts(synthetic_continue)
        if not all(
            isinstance(info, dict)
            for info in (compaction_info, summary_info, continue_info)
        ):
            return False
        if not all(
            isinstance(parts, list)
            for parts in (compaction_parts, summary_parts, continue_parts)
        ):
            return False
        if len(compaction_parts) != 1 or len(continue_parts) != 1:
            return False

        compaction_part = compaction_parts[0]
        continue_part = continue_parts[0]
        if not isinstance(compaction_part, dict) or not isinstance(continue_part, dict):
            return False
        compaction_id = compaction_info.get("id")
        continue_id = continue_info.get("id")
        overflow = compaction_part.get("overflow")
        return bool(
            isinstance(compaction_id, str)
            and compaction_id
            and isinstance(summary_info.get("id"), str)
            and summary_info["id"]
            and isinstance(continue_id, str)
            and continue_id
            and isinstance(overflow, bool)
            and compaction_info.get("role") == "user"
            and "summary" not in compaction_info
            and compaction_part.get("type") == "compaction"
            and compaction_part.get("auto") is True
            and compaction_part.get("messageID") == compaction_id
            and summary_info.get("role") == "assistant"
            and summary_info.get("summary") is True
            and summary_info.get("mode") == "compaction"
            and summary_info.get("agent") == "compaction"
            and summary_info.get("parentID") == compaction_id
            and all(
                isinstance(part, dict) and part.get("type") != "compaction"
                for part in summary_parts
            )
            and continue_info.get("role") == "user"
            and "summary" not in continue_info
            and continue_part.get("type") == "text"
            and continue_part.get("text")
            == opencode_synthetic_continue(overflow=overflow)
            and continue_part.get("synthetic") is True
            and continue_part.get("metadata") == {"compaction_continue": True}
            and continue_part.get("messageID") == continue_id
        )

    @classmethod
    def _export_post_compaction_assistant(
        cls, assistant: Any, synthetic_continue: Any
    ) -> bool:
        continue_info = cls._export_info(synthetic_continue)
        assistant_info = cls._export_info(assistant)
        return bool(
            isinstance(continue_info, dict)
            and isinstance(continue_info.get("id"), str)
            and continue_info["id"]
            and cls._export_regular_assistant(assistant)
            and isinstance(assistant_info, dict)
            and assistant_info.get("parentID") == continue_info["id"]
        )

    @classmethod
    def _export_tail_is_valid(cls, tail: list[Any], *, prompt: str) -> bool:
        return cls._reflection_tail_state_machine(
            tail,
            is_prompt=lambda message: cls._export_exact_user_text(
                message,
                matches=lambda text: cls._opencode_exported_prompt_matches(
                    text, prompt
                ),
            ),
            is_regular_assistant=cls._export_regular_assistant,
            is_compaction_sequence=cls._export_compaction_sequence,
            is_post_compaction_assistant=cls._export_post_compaction_assistant,
        )

    @classmethod
    def _verify_export_continuity(
        cls,
        solve: dict[str, Any],
        full: dict[str, Any],
        *,
        prompt: str,
        task_id: str,
    ) -> str:
        solve_id = cls._session_id_from_export(solve, task_id=task_id)
        full_id = cls._session_id_from_export(full, task_id=task_id)
        solve_messages = solve.get("messages")
        full_messages = full.get("messages")
        if (
            solve_id != full_id
            or not isinstance(solve_messages, list)
            or not isinstance(full_messages, list)
            or full_messages[: len(solve_messages)] != solve_messages
        ):
            raise UnscoreableTrialError(
                "reflection-export-prefix-mismatch", task_id=task_id
            )
        tail = full_messages[len(solve_messages) :]
        if not cls._export_tail_is_valid(tail, prompt=prompt):
            raise UnscoreableTrialError(
                "reflection-export-tail-invalid", task_id=task_id
            )
        return full_id

    @staticmethod
    def _hash_tree_nofollow(root: Path, *, task_id: str) -> str:
        if not root.is_dir() or root.is_symlink():
            raise UnscoreableTrialError(
                "reflection-task-snapshot-invalid", task_id=task_id
            )
        digest = hashlib.sha256()

        def visit(directory: Path, relative: Path) -> None:
            try:
                entries = sorted(os.scandir(directory), key=lambda item: item.name)
            except OSError as exc:
                raise UnscoreableTrialError(
                    "reflection-task-snapshot-invalid",
                    task_id=task_id,
                    exception_type=type(exc).__name__,
                ) from exc
            for entry in entries:
                rel = relative / entry.name
                metadata = entry.stat(follow_symlinks=False)
                rel_bytes = rel.as_posix().encode("utf-8", errors="surrogateescape")
                mode = stat.S_IMODE(metadata.st_mode)
                if stat.S_ISDIR(metadata.st_mode):
                    digest.update(
                        b"D\0" + rel_bytes + b"\0" + str(mode).encode() + b"\0"
                    )
                    visit(Path(entry.path), rel)
                elif stat.S_ISREG(metadata.st_mode):
                    digest.update(
                        b"F\0" + rel_bytes + b"\0" + str(mode).encode() + b"\0"
                    )
                    file_digest = hashlib.sha256()
                    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                    try:
                        fd = os.open(entry.path, flags)
                        try:
                            opened = os.fstat(fd)
                            if not stat.S_ISREG(opened.st_mode):
                                raise OSError("task file changed type while hashing")
                            while chunk := os.read(fd, 1024 * 1024):
                                file_digest.update(chunk)
                        finally:
                            os.close(fd)
                    except OSError as exc:
                        raise UnscoreableTrialError(
                            "reflection-task-snapshot-invalid",
                            task_id=task_id,
                            exception_type=type(exc).__name__,
                        ) from exc
                    digest.update(file_digest.digest())
                elif stat.S_ISLNK(metadata.st_mode):
                    target = os.readlink(entry.path)
                    digest.update(
                        b"L\0"
                        + rel_bytes
                        + b"\0"
                        + str(mode).encode()
                        + b"\0"
                        + target.encode("utf-8", errors="surrogateescape")
                        + b"\0"
                    )
                else:
                    raise UnscoreableTrialError(
                        "reflection-task-snapshot-special-file", task_id=task_id
                    )

        visit(root, Path())
        return digest.hexdigest()

    @classmethod
    def _copy_tree_nofollow(
        cls, source: Path, destination: Path, *, task_id: str
    ) -> None:
        if not source.is_dir() or source.is_symlink() or os.path.lexists(destination):
            raise UnscoreableTrialError(
                "reflection-verifier-snapshot-invalid", task_id=task_id
            )
        destination.mkdir(mode=0o700)
        for entry in sorted(os.scandir(source), key=lambda item: item.name):
            src = Path(entry.path)
            dst = destination / entry.name
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                cls._copy_tree_nofollow(src, dst, task_id=task_id)
            elif stat.S_ISREG(metadata.st_mode):
                raw = cls._read_regular_nofollow(
                    src,
                    max_bytes=_MAX_AUDIT_FILE_BYTES,
                    task_id=task_id,
                    reason="reflection-verifier-snapshot-invalid",
                )
                cls._write_new_regular(dst, raw, task_id)
            else:
                raise UnscoreableTrialError(
                    "reflection-verifier-snapshot-special-file", task_id=task_id
                )

    @classmethod
    def _copy_task_tree_nofollow(
        cls, source: Path, destination: Path, *, task_id: str
    ) -> None:
        """Copy a task snapshot without following agent-authored symlinks."""

        if not source.is_dir() or source.is_symlink() or os.path.lexists(destination):
            raise UnscoreableTrialError("repair-task-snapshot-invalid", task_id=task_id)
        source_mode = stat.S_IMODE(source.stat(follow_symlinks=False).st_mode)
        destination.mkdir(mode=0o700)
        for entry in sorted(os.scandir(source), key=lambda item: item.name):
            src = Path(entry.path)
            dst = destination / entry.name
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                cls._copy_task_tree_nofollow(src, dst, task_id=task_id)
            elif stat.S_ISREG(metadata.st_mode):
                flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
                try:
                    fd = os.open(src, flags)
                    try:
                        opened = os.fstat(fd)
                        if not stat.S_ISREG(opened.st_mode):
                            raise OSError("task file changed type while copying")
                        raw_chunks: list[bytes] = []
                        while chunk := os.read(fd, 1024 * 1024):
                            raw_chunks.append(chunk)
                    finally:
                        os.close(fd)
                except OSError as exc:
                    raise UnscoreableTrialError(
                        "repair-task-snapshot-invalid",
                        task_id=task_id,
                        exception_type=type(exc).__name__,
                    ) from exc
                cls._write_new_regular(dst, b"".join(raw_chunks), task_id)
                os.chmod(dst, stat.S_IMODE(metadata.st_mode))
            elif stat.S_ISLNK(metadata.st_mode):
                try:
                    os.symlink(os.readlink(src), dst)
                except OSError as exc:
                    raise UnscoreableTrialError(
                        "repair-task-snapshot-invalid",
                        task_id=task_id,
                        exception_type=type(exc).__name__,
                    ) from exc
            else:
                raise UnscoreableTrialError(
                    "repair-task-snapshot-special-file", task_id=task_id
                )
        # The audit hash intentionally covers permission bits as well as file
        # contents.  ``mkdir(mode=0o700)`` keeps a partially copied tree private,
        # then the final chmod faithfully restores the source directory mode.
        # Without this, nested task directories such as ``middleware/`` (0775)
        # are silently changed to 0700 and the post-copy integrity check fails.
        os.chmod(destination, source_mode)

    @staticmethod
    def _empty_directory(path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)
        for child in path.iterdir():
            if child.is_symlink() or not child.is_dir():
                child.unlink(missing_ok=True)
            else:
                shutil.rmtree(child)

    @classmethod
    def _snapshot_and_hide_verifier(
        cls, trial: Any, *, audit_dir: Path, task_id: str
    ) -> Path:
        verifier_dir = Path(trial.paths.verifier_dir)
        official = audit_dir / "official-verifier"
        cls._copy_tree_nofollow(verifier_dir, official, task_id=task_id)
        cls._empty_directory(verifier_dir)
        return official

    @classmethod
    def _restore_verifier_evidence(
        cls,
        trial: Any,
        *,
        official_verifier: Path,
        audit_dir: Path,
        task_id: str,
    ) -> None:
        verifier_dir = Path(trial.paths.verifier_dir)
        if any(verifier_dir.iterdir()):
            cls._copy_tree_nofollow(
                verifier_dir,
                audit_dir / "reflection-verifier-noise",
                task_id=task_id,
            )
        cls._empty_directory(verifier_dir)
        # Copy rather than move: the host-only audit remains the canonical
        # immutable record even after Harbor's conventional path is restored.
        for entry in sorted(os.scandir(official_verifier), key=lambda item: item.name):
            source = Path(entry.path)
            destination = verifier_dir / entry.name
            metadata = entry.stat(follow_symlinks=False)
            if stat.S_ISDIR(metadata.st_mode):
                cls._copy_tree_nofollow(source, destination, task_id=task_id)
            elif stat.S_ISREG(metadata.st_mode):
                raw = cls._read_regular_nofollow(
                    source,
                    max_bytes=_MAX_AUDIT_FILE_BYTES,
                    task_id=task_id,
                    reason="reflection-verifier-restore-invalid",
                )
                cls._write_new_regular(destination, raw, task_id)
            else:
                raise UnscoreableTrialError(
                    "reflection-verifier-restore-invalid", task_id=task_id
                )

    @classmethod
    async def _restart_main_and_prove(cls, trial: Any, *, task_id: str) -> None:
        restart = getattr(trial.agent_environment, "restart_main_service", None)
        identity = getattr(trial.agent_environment, "main_service_identity", None)
        if not callable(restart) or not callable(identity):
            raise UnscoreableTrialError(
                "reflection-environment-cannot-restart-same-container",
                task_id=task_id,
            )
        await restart()
        trial._sevb_agent_main_stopped = False
        restarted_identity = await identity()
        running_identity = await cls._main_running_identity(trial, task_id=task_id)
        expected_identity = getattr(trial, "_sevb_agent_container_identity", None)
        if (
            not expected_identity
            or restarted_identity != expected_identity
            or running_identity != expected_identity
        ):
            raise UnscoreableTrialError(
                "reflection-container-identity-changed", task_id=task_id
            )
        healthcheck = getattr(trial.agent_environment, "run_healthcheck", None)
        if callable(healthcheck):
            await healthcheck()

    @staticmethod
    async def _main_running_identity(trial: Any, *, task_id: str) -> str:
        running = getattr(
            trial.agent_environment, "main_service_running_identity", None
        )
        if not callable(running):
            raise UnscoreableTrialError(
                "reflection-environment-cannot-prove-main-stopped",
                task_id=task_id,
            )
        try:
            return str(await running() or "").strip()
        except BaseException as exc:
            raise UnscoreableTrialError(
                "reflection-main-state-query-failed",
                task_id=task_id,
                exception_type=type(exc).__name__,
            ) from exc

    @classmethod
    async def _require_main_not_running(cls, trial: Any, *, task_id: str) -> None:
        if await cls._main_running_identity(trial, task_id=task_id):
            raise UnscoreableTrialError(
                "reflection-main-still-running", task_id=task_id
            )

    @classmethod
    async def _stop_main_and_prove(cls, trial: Any, *, task_id: str) -> None:
        stop_error: BaseException | None = None
        try:
            await trial.agent_environment.stop_service("main")
        except BaseException as exc:
            stop_error = exc
        await cls._require_main_not_running(trial, task_id=task_id)
        trial._sevb_agent_main_stopped = True
        if stop_error is not None:
            raise UnscoreableTrialError(
                "reflection-main-stop-failed",
                task_id=task_id,
                exception_type=type(stop_error).__name__,
            ) from stop_error

    async def _on_shadow_trial_started(
        self,
        event: "TrialHookEvent",
        task: Any,
        runtime_basename: str,
    ) -> None:
        """Dual-T6 shadow: build instruction.md at the shadow dir using
        OracleRetriever (required_skills) and cache pre-state under a
        shadow-suffixed key so the ended hook can recover it.

        Library is frozen at this point (we're inside the eval block of
        the env that just produced the primary T6 trial), so the second
        retrieval/agent-run sees the identical library state -- the
        comparison is paired-by-trial.
        """
        # Build a fresh OracleRetriever; falls back to the runtime's
        # primary retriever for non-T6 (defensive -- shadows are only
        # scheduled for T6 anyway).
        from skillevolbench.components.retriever import OracleRetriever

        oracle = OracleRetriever(
            task_registry=self.task_registry,
            inner=self.runtime.retriever,
        )
        instruction_text = self._read_instruction(task)
        retrieval = oracle.retrieve(
            query=instruction_text,
            library=self.runtime.library,
            k=self.runtime.baseline.skill_retrieval_k,
            task_id=task.task_id,
        )

        # Build instruction.md + injection-context.json at the shadow's
        # own runtime dir (RuntimeBuilder uses task.task_id by default;
        # for the shadow we need the suffixed dir, so we patch
        # ``task.task_id`` momentarily via a small wrapper object).
        from types import SimpleNamespace

        shadow_task = SimpleNamespace(
            task_id=runtime_basename,  # <task_id>__oracle_shadow
            task_slug=task.task_slug,
            family_id=task.family_id,
            environment_id=task.environment_id,
            role=task.role,
            phase=task.phase,
            harbor=task.harbor,
            required_skills=task.required_skills,
            latent_skill_id=task.latent_skill_id,
        )
        runtime_task_dir = self.runtime_builder.build(
            task=shadow_task,
            run_root=self.runtime.run_root,
            baseline=self.runtime.baseline,
            retrieved_skills=(retrieval.skills if retrieval else []),
            retrieved_trajectories=[],  # shadow does not see traj RAG
            history_context=None,  # shadow does not see history
            library_frozen=True,  # always frozen (we're at T6 eval)
            runtime_basename=runtime_basename,
        )

        # Cache pre-state under the shadow-suffixed key.
        self._pre_state_cache[runtime_basename] = {
            "library_hash": self.runtime.library.compute_hash(),
            "retrieval": retrieval,
            "runtime_dir": runtime_task_dir,
            "started_at": datetime.now(timezone.utc),
            "is_shadow": True,
        }

        self.runtime.event_store.record(
            "shadow_trial_started",
            {
                "task_id": task.task_id,
                "shadow_runtime": runtime_basename,
                "library_hash": self.runtime.library.compute_hash(),
                "retrieved_skill_ids": (
                    [s.skill_id for s in retrieval.skills] if retrieval else []
                ),
            },
        )

    # ==================================================================
    # HOOK 2: on_trial_ended
    # ==================================================================

    async def on_trial_ended(self, event: "TrialHookEvent") -> None:
        """Post-trial: parse outcome, persist replay, dispatch to strategy."""
        if event.result is None:
            self.runtime.event_store.record(
                "trial_ended_no_result", {"task_name": getattr(event, "task_name", "?")}
            )
            raise UnscoreableTrialError(
                "missing-trial-result",
                task_id=self._runtime_basename(event) or "?",
            )
        # Run the substantive logic in a worker thread so we don't block
        # Harbor's event loop while doing sqlite + git work.
        await asyncio.to_thread(self._on_trial_ended_sync, event)

    def _on_trial_ended_sync(self, event: "TrialHookEvent") -> None:
        task = self._resolve_task(event)
        runtime_basename = self._runtime_basename(event)
        is_shadow = _is_shadow_trial_name(runtime_basename)
        is_replay = _is_replay_trial_name(runtime_basename)
        # Pre-state was cached under the runtime-dir basename so primary
        # and shadow / replay records of the same task_id don't alias.
        cache_key = runtime_basename if (is_shadow or is_replay) else task.task_id
        pre_state = self._pre_state_cache.pop(cache_key, None)
        if pre_state is None:
            self.runtime.event_store.record(
                "orphan_trial_ended",
                {"task_id": task.task_id, "is_shadow": is_shadow},
            )
            raise UnscoreableTrialError(
                "missing-trial-pre-state",
                task_id=task.task_id,
            )
        reflection_record = self._reflection_cache.pop(cache_key, None)

        # 1. Parse verifier output (Part 6 VerifierAdapter).  ``parse`` is a
        # fail-closed boundary: agent/runtime exceptions, missing verifier
        # state, a missing canonical reward, or a missing trajectory abort the
        # whole episode here.  Crucially this happens before ReplayStore,
        # strategy.decide(), or any library mutation, so infrastructure
        # failures can never masquerade as reward=0 learning experience.
        try:
            outcome = self.runtime.verifier_adapter.parse(event.result)
        except UnscoreableTrialError as exc:
            self.runtime.event_store.record(
                "trial_rejected_unscoreable",
                {
                    "task_id": task.task_id,
                    "reason": exc.reason,
                    "exception_type": exc.exception_type,
                },
            )
            raise

        # The complete same-session trajectory is retained as the canonical
        # user-facing audit artifact. Task behavior metrics must remain based
        # on the solve turn only; otherwise reflection-time reads of /skills
        # would be misclassified as skills used to solve the task.
        full_session_trajectory: Path | None = None
        if (
            self.runtime.baseline.skill_update_source == "same_agent_session"
            and not is_shadow
            and not is_replay
            and task.role in {r.value for r in _LEARNING_ROLES}
        ):
            if reflection_record is None:
                raise UnscoreableTrialError(
                    "missing-reflection-record", task_id=task.task_id
                )
            # Only attempted reflections have a second turn. Their trusted
            # solve/full trajectories live in the host-only audit directory;
            # never derive them from an agent-writable artifact path. A
            # deliberately skipped reflection keeps the ordinary solve path.
            if reflection_record.status in {"completed", "noop", "rejected"}:
                solve_path = reflection_record.solve_trajectory_path
                full_session_trajectory = reflection_record.full_session_trajectory_path
                if (
                    solve_path is None
                    or full_session_trajectory is None
                    or not solve_path.is_file()
                    or not full_session_trajectory.is_file()
                ):
                    raise UnscoreableTrialError(
                        "missing-reflection-audit-trajectory", task_id=task.task_id
                    )
                outcome = outcome.model_copy(update={"trajectory_path": solve_path})
            elif reflection_record.status != "skipped":
                raise UnscoreableTrialError(
                    "invalid-reflection-status", task_id=task.task_id
                )

        # 2. Extract actually-used skills from the trajectory.
        skills_used = self.runtime.trajectory_extractor.extract_skills_used(
            outcome.trajectory_path,
            library=self.runtime.library,
        )

        # 3. Compact trajectory in TWO modes for replay store:
        #   (a) RICH -- preserves reasoning + full obs, fed into SkillAuthor's
        #       cumulative-trace input for revision/induction.
        #   (b) ROUGH -- drops reasoning, brief obs, smaller budget. Fed into
        #       TrajectoryRetriever (raw_trajectory_rag baseline). Keeping
        #       these separate ensures the "raw episodic experience" baseline
        #       doesn't silently inherit abstraction-friendly preprocessing.
        compacted = self.runtime.compactor.compact(
            outcome.trajectory_path,
            outcome=outcome,
        )
        compacted_rough = self.runtime.compactor_rough.compact(
            outcome.trajectory_path,
            outcome=outcome,
        )

        # 4. Persist ReplayRecord (Part 5 ReplayStore).
        from skillevolbench.schemas.replay import ReplayRecord  # lazy: stub-safe

        # Choose record_task_id so original/shadow/replay records don't
        # alias under the same key. Shadow records use runtime_basename
        # (suffixed with __oracle_shadow); replay records similarly use
        # the __replay-suffixed runtime_basename.
        if is_shadow or is_replay:
            record_task_id = runtime_basename
        else:
            record_task_id = task.task_id
        # Mode tag distinguishes record types at metric-aggregation time.
        if is_shadow:
            mode = "shadow_oracle"
        elif is_replay:
            mode = "within_env_replay"
        else:
            mode = "primary"
        record = ReplayRecord(
            task_id=record_task_id,
            family_id=task.family_id,
            env_id=task.environment_id,
            task_role=task.role,
            timestamp=datetime.now(timezone.utc),
            library_hash_pre=pre_state["library_hash"],
            library_hash_post=self.runtime.library.compute_hash(),
            outcome=outcome,
            retrieval=pre_state["retrieval"],
            skills_actually_used=skills_used,
            trajectory_compact=compacted.to_dict(),
            trajectory_compact_rough=compacted_rough.to_dict(),
            replay_mode=mode,
            reflection=(
                {
                    **reflection_record.to_dict(),
                    "solve_trajectory_path": str(outcome.trajectory_path),
                    "full_session_trajectory_path": (
                        str(full_session_trajectory)
                        if full_session_trajectory is not None
                        else None
                    ),
                }
                if reflection_record is not None
                else {}
            ),
        )
        self.runtime.replay_store.persist(record)

        # Shadow trials short-circuit: no eval-buffer push (would alias
        # the primary's metrics), no strategy.decide, no maintenance.
        if is_shadow:
            self._assert_freeze_invariant(task)
            self.runtime.event_store.record(
                "shadow_trial_ended",
                {
                    "task_id": task.task_id,
                    "shadow_runtime": runtime_basename,
                    "verifier_passed": outcome.verifier_passed,
                    "reward": outcome.reward,
                },
            )
            return

        # Replay trials short-circuit similarly: persist for metric
        # computation (replay_pass_rate vs original_pass_rate -> evolution
        # lift) but skip strategy.decide entirely. The library is frozen
        # at the env's post-evolution state, and replays are designed to
        # observe it without mutating it. ``_assert_freeze_invariant``
        # confirms the library actually stayed frozen across the replay.
        if is_replay:
            self._assert_freeze_invariant(task)
            self.runtime.event_store.record(
                "replay_trial_ended",
                {
                    "task_id": task.task_id,
                    "replay_runtime": runtime_basename,
                    "env_id": task.environment_id,
                    "verifier_passed": outcome.verifier_passed,
                    "reward": outcome.reward,
                },
            )
            return

        # 5. Eval block: skip strategy entirely + assert freeze invariant.
        if task.role in {r.value for r in _EVAL_ROLES}:
            self._eval_outcomes_buffer.append(record)
            self._assert_freeze_invariant(task)
            self.runtime.event_store.record(
                "trial_ended_eval",
                {
                    "task_id": task.task_id,
                    "verifier_passed": outcome.verifier_passed,
                    "reward": outcome.reward,
                },
            )
            return

        # 6. Learning block: build context + dispatch to strategy.
        from skillevolbench.strategies.base import (  # lazy: stub-safe at runtime
            ApplyPatch,
            EvolutionContext,
        )

        if self.runtime.baseline.skill_update_source == "same_agent_session":
            assert reflection_record is not None
            if reflection_record.patch is not None:
                self.runtime.event_store.record_patch_proposed(
                    reflection_record.patch, "in_session_reflection"
                )
                decision = ApplyPatch(patch=reflection_record.patch)
            else:
                from skillevolbench.strategies.base import NoOp

                decision = NoOp(
                    reason=(
                        f"reflection_{reflection_record.status}:"
                        f"{reflection_record.reason or 'no_patch'}"
                    )
                )
        else:
            ctx = EvolutionContext(
                task=task,
                outcome=outcome,
                compacted=compacted,
                pre_retrieval=pre_state["retrieval"],
                skills_actually_used=skills_used,
                baseline=self.runtime.baseline,
                replay_store=self.runtime.replay_store,
                library=self.runtime.library,
            )
            decision = self.runtime.strategy.decide(ctx)

        # 7. Apply / NoOp -- all writes go through freeze_ctrl.
        # (Rollback decision was an RGPE-only path; removed.)
        if isinstance(decision, ApplyPatch):
            strategy_name = (
                "in_session_reflection"
                if self.runtime.baseline.skill_update_source == "same_agent_session"
                else self.runtime.strategy.name
            )
            self.runtime.freeze_ctrl.submit_patch(
                patch=decision.patch,
                strategy_name=strategy_name,
                current_task=task.task_id,
            )
        else:  # NoOp
            self.runtime.event_store.record(
                "noop_decision",
                {"task_id": task.task_id, "reason": decision.reason},
            )

        self.runtime.event_store.record(
            "trial_ended_learning",
            {
                "task_id": task.task_id,
                "verifier_passed": outcome.verifier_passed,
                "decision_type": type(decision).__name__,
                "reflection_status": (
                    reflection_record.status if reflection_record else None
                ),
                "library_hash_after": self.runtime.library.compute_hash(),
            },
        )

        # 8. Freeze BEFORE the first T4's container is constructed.
        # Harbor builds the trial environment in ``Trial.__init__``
        # (harbor/trial/trial.py), which runs BEFORE TrialEvent.START
        # fires. ``GlobalLibraryEnvironment.__init__`` reads the
        # ``.frozen`` marker once at that moment to decide whether the 5
        # skill mounts should be ``read_only=True``. If we wait until
        # T4's START hook to write the marker, T4's mounts are already
        # baked as read-write.
        #
        # The schedule (scheduler.py) is::
        #
        #     env learning block:  LS1[T1,T2,T3], LS2[T1,T2,T3], ..., LS5[T1,T2,T3]
        #     env eval block:      LS1[T4,T5,T6], ..., LS5[T4,T5,T6]
        #
        # So we must NOT freeze at every T3 ended (LS1-T3 ended is
        # followed by LS2-T1 which still needs to inject_curated). The
        # right moment is "the last LEARNING task of this env just
        # finished". We count completed learning trials per env and
        # freeze when the count reaches ``len(families_in_env) * 3``
        # (3 learning roles per family).
        #
        # Idempotent with the T4-START fallback in ``on_trial_started``
        # (covers orphan-trial-ended edge cases).
        if task.role in {r.value for r in _LEARNING_ROLES}:
            env_id = task.environment_id
            self._learning_completed_per_env[env_id] = (
                self._learning_completed_per_env.get(env_id, 0) + 1
            )
            n_families_in_env = len(self.task_registry.families_in_env(env_id))
            target = n_families_in_env * 3  # 3 learning roles per family
            if (
                self._learning_completed_per_env[env_id] >= target
                and not self.runtime.freeze_ctrl.frozen
            ):
                self.runtime.freeze_ctrl.freeze(env_id)

    # ==================================================================
    # Env transition handler
    # ==================================================================

    async def _handle_env_transition(self, prev_env: str, new_env: str) -> None:
        """Called after the last task of ``prev_env`` -- runs unfreeze +
        post-eval maintenance + tags a snapshot. Optionally clears the
        active library when ``baseline.library_scope == "environment"``.
        """
        self.runtime.freeze_ctrl.unfreeze_and_maintain(
            env_id=prev_env,
            baseline=self.runtime.baseline,
            eval_records=self._eval_outcomes_buffer,
        )
        self._eval_outcomes_buffer.clear()

        # Tag a per-env snapshot before clearing the active library.
        # IMPORTANT: this MUST happen BEFORE clear_active below -- once the
        # working tree is wiped, the snapshot tag would point at the post-
        # wipe (empty) state instead of the env's final state.
        if self.runtime.snapshot_store is not None:
            self.runtime.snapshot_store.tag(f"after-{prev_env}")

        # Per-env physical isolation (library_scope=="environment"):
        # each env has its own LibraryStore at ``library/<env_id>/`` with
        # its own git repo + manifest. No "reset" / "wipe" is needed --
        # the next env's first task calls ``switch_env(new_env)`` which
        # lazy-inits ``library/<new_env>/`` (empty by construction).
        # ``runtime.library`` is then swapped to that LibraryStore and
        # inject_curated / induce_skill / zero_shot_create see the new
        # env's empty library and re-seed naturally. We just record the
        # event for audit.
        scope = getattr(self.runtime.baseline, "library_scope", "global")
        if scope == "environment":
            self.runtime.event_store.record(
                "library_swap_on_env_transition",
                {
                    "from_env": prev_env,
                    "to_env": new_env,
                    "from_env_library_path": str(
                        getattr(
                            self.runtime,
                            "library_root",
                            self.runtime.run_root / "library",
                        )
                        / prev_env
                    ),
                },
            )

        self.runtime.event_store.record(
            "env_transition",
            {
                "from_env": prev_env,
                "to_env": new_env,
                "library_hash": self.runtime.library.compute_hash(),
            },
        )

    # ==================================================================
    # Internal helpers (also unit-test seams)
    # ==================================================================

    def _resolve_task(self, event: "TrialHookEvent") -> Any:
        """Recover the ``TaskSpec`` for the trial that fired this event.

        Harbor 0.6+ sets ``TrialHookEvent.task_name`` to ``TaskConfig.name``
        (auto-derived from the basename of ``TaskConfig.path``). We arrange
        the runtime layout as ``runtime/<task_id>/`` (no extra subdir), so
        the basename IS ``task_id`` and we look it up directly.

        Dual-T6 shadow trials use ``runtime/<task_id>__oracle_shadow/``;
        we strip that suffix before registry lookup so the same TaskSpec
        is returned for both primary and shadow.

        Defensive fallback: if a fixture (or older Harbor version) passes
        a path-shaped value containing ``runtime/<task_id>/...``, extract
        the ``<task_id>`` segment.
        """
        raw = str(getattr(event, "task_name", "") or "")
        # Path-shaped fallback (legacy / fixture inputs).
        if "/" in raw or "\\" in raw:
            parts = Path(raw).parts
            # Old layout: .../runtime/<task_id>/harbor-task-copy
            if "harbor-task-copy" in parts:
                idx = parts.index("harbor-task-copy")
                if idx > 0:
                    raw = parts[idx - 1]
            # New layout: .../runtime/<task_id>
            elif "runtime" in parts:
                idx = parts.index("runtime")
                if idx + 1 < len(parts):
                    raw = parts[idx + 1]
            else:
                raw = Path(raw).name
        if not raw:
            raise KeyError(
                f"Could not resolve task_id from TrialHookEvent.task_name="
                f"{getattr(event, 'task_name', None)!r}"
            )
        # Strip dual-T6 shadow / within-env replay suffixes before
        # registry lookup -- both share a TaskSpec with their original.
        canonical = raw
        if canonical.endswith(_SHADOW_T6_SUFFIX):
            canonical = canonical[: -len(_SHADOW_T6_SUFFIX)]
        if canonical.endswith(_REPLAY_SUFFIX):
            canonical = canonical[: -len(_REPLAY_SUFFIX)]
        return self.task_registry.task(canonical).spec

    def _runtime_basename(self, event: "TrialHookEvent") -> str:
        """Return the runtime-dir basename for this trial (with any
        ``__oracle_shadow`` suffix preserved). Used to detect dual-T6
        shadow trials."""
        raw = str(getattr(event, "task_name", "") or "")
        if "/" in raw or "\\" in raw:
            parts = Path(raw).parts
            if "harbor-task-copy" in parts:
                idx = parts.index("harbor-task-copy")
                if idx > 0:
                    raw = parts[idx - 1]
            elif "runtime" in parts:
                idx = parts.index("runtime")
                if idx + 1 < len(parts):
                    raw = parts[idx + 1]
            else:
                raw = Path(raw).name
        return raw

    def _read_instruction(self, task: Any) -> str:
        """Read the original (non-injected) instruction text from disk.

        We pass the *original* text to the retriever so the retrieval query
        is independent of any baseline-specific injection. The injected
        version goes into the *runtime* copy that the agent reads.
        """
        # Falling back: ask the registry record for the resolved folder.
        record = self.task_registry.task(task.task_id)
        instr_path = record.folder / record.spec.harbor.instruction
        return instr_path.read_text()

    def _inject_curated_v0(self, task: Any) -> None:
        """Path-B: copy the curated SKILL.md into the live library."""
        family = self.task_registry.family(task.family_id)
        curated_path = family.folder / family.meta.curated_skill_path
        if not curated_path.exists():
            raise FileNotFoundError(
                f"Path-B baseline {self.runtime.baseline.name!r} expects curated "
                f"SKILL.md at {curated_path} but it is missing"
            )
        self.runtime.library.inject_curated(
            skill_md_path=curated_path,
            family_id=task.family_id,
            latent_skill_id=task.latent_skill_id,
            created_from_task=task.task_id,
        )
        self.runtime.event_store.record(
            "curated_seeded",
            {"family_id": task.family_id, "task_id": task.task_id},
        )

    def _seed_curated_environment(self, env_id: str, triggered_by_task: str) -> None:
        """Seed curated skills required by an eval-only control.

        The exact-oracle condition seeds the target environment's five skills.
        The shuffled negative control additionally seeds the next environment's
        five skills, then exposes only that disjoint subset per task.
        """
        if env_id in self._oracle_seeded_envs:
            return
        target_families = list(self.task_registry.families_in_env(env_id))
        if len(target_families) != 5:
            raise RuntimeError(
                f"oracle diagnostic expected five families in {env_id}; "
                f"got {len(target_families)}"
            )
        families = list(target_families)
        shuffled_env_id: str | None = None
        if self.runtime.run_config.shuffled_skill_view:
            env_number = int(env_id[1:])
            shuffled_env_id = f"E{env_number % 6 + 1}"
            shuffled_families = list(
                self.task_registry.families_in_env(shuffled_env_id)
            )
            if len(shuffled_families) != 5:
                raise RuntimeError(
                    "shuffled diagnostic expected five source families in "
                    f"{shuffled_env_id}; got {len(shuffled_families)}"
                )
            families.extend(shuffled_families)
        for family in families:
            if self.runtime.library.has_curated_for(family.meta.family_id):
                continue
            curated_path = family.folder / family.meta.curated_skill_path
            if not curated_path.is_file():
                raise FileNotFoundError(
                    f"oracle diagnostic is missing curated skill {curated_path}"
                )
            self.runtime.library.inject_curated(
                skill_md_path=curated_path,
                family_id=family.meta.family_id,
                latent_skill_id=family.meta.latent_skill_id,
                created_from_task=triggered_by_task,
            )
            self.runtime.event_store.record(
                "curated_seeded",
                {
                    "family_id": family.meta.family_id,
                    "task_id": triggered_by_task,
                    "diagnostic_preseed": True,
                    "shuffled_source_environment": shuffled_env_id,
                },
            )
        self._oracle_seeded_envs.add(env_id)
        self.runtime.event_store.record(
            "oracle_environment_seeded",
            {
                "environment_id": env_id,
                "task_id": triggered_by_task,
                "n_curated_skills": len(families),
                "shuffled_source_environment": shuffled_env_id,
                "library_hash": self.runtime.library.compute_hash(),
            },
        )

    def _stage_oracle_skill_view(self, task: Any, runtime_basename: str) -> None:
        """Expose exactly the annotated gold skill subset for one eval task."""
        from skillevolbench.stores.library_store import skill_id_to_slug

        skill_ids = (
            list(task.required_skills)
            if task.role == TaskRole.COMPOSITION.value
            else [task.primary_skill]
        )
        if not skill_ids:
            raise RuntimeError(
                f"oracle diagnostic task {task.task_id} has no annotated skills"
            )
        if len(skill_ids) != len(set(skill_ids)):
            raise RuntimeError(
                f"oracle diagnostic task {task.task_id} has duplicate skill ids"
            )

        views_root = self.runtime.run_root / "oracle-skill-views"
        view_dir = views_root / runtime_basename
        view_dir.mkdir(parents=True, exist_ok=True)
        for child in list(view_dir.iterdir()):
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                raise RuntimeError(f"unsupported object in oracle view: {child}")

        copied: list[dict[str, Any]] = []
        for skill_id in skill_ids:
            family_id = skill_id.split(".", 1)[0]
            family = self.task_registry.family(family_id)
            if family.meta.latent_skill_id != skill_id:
                raise RuntimeError(
                    f"oracle annotation {skill_id!r} does not match family metadata"
                )
            slug = skill_id_to_slug(skill_id)
            source = self.runtime.library.active_dir / slug
            if not source.is_dir() or source.is_symlink():
                raise RuntimeError(
                    f"curated library content for {skill_id!r} is unavailable"
                )
            for path in source.rglob("*"):
                if path.is_symlink():
                    raise RuntimeError(
                        f"oracle skill {skill_id!r} contains a forbidden symlink"
                    )
            destination = view_dir / slug
            shutil.copytree(source, destination)
            digest = hashlib.sha256()
            for path in sorted(
                (item for item in destination.rglob("*") if item.is_file()),
                key=lambda item: item.relative_to(destination).as_posix(),
            ):
                relative = path.relative_to(destination).as_posix()
                digest.update(relative.encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
            copied.append(
                {
                    "skill_id": skill_id,
                    "slug": slug,
                    "sha256": digest.hexdigest(),
                }
            )

        audit = {
            "schema_version": 1,
            "task_id": task.task_id,
            "runtime_basename": runtime_basename,
            "role": task.role,
            "oracle_skill_ids": skill_ids,
            "skills": copied,
            "library_hash": self.runtime.library.compute_hash(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        audit_path = views_root / f"{runtime_basename}.audit.json"
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.runtime.event_store.record(
            "oracle_skill_view_staged",
            {
                "task_id": task.task_id,
                "oracle_skill_ids": skill_ids,
                "library_hash": audit["library_hash"],
            },
        )

    def _stage_shuffled_skill_view(self, task: Any, runtime_basename: str) -> None:
        """Expose an equal-count, cross-environment unrelated skill subset."""
        from skillevolbench.stores.library_store import skill_id_to_slug

        gold_skill_ids = (
            list(task.required_skills)
            if task.role == TaskRole.COMPOSITION.value
            else [task.primary_skill]
        )
        if not gold_skill_ids or len(gold_skill_ids) != len(set(gold_skill_ids)):
            raise RuntimeError(
                f"shuffled diagnostic task {task.task_id} has invalid gold skills"
            )
        target_env_number = int(task.environment_id[1:])
        source_env_id = f"E{target_env_number % 6 + 1}"
        mappings: list[tuple[str, str]] = []
        for gold_skill_id in gold_skill_ids:
            gold_family_id = gold_skill_id.split(".", 1)[0]
            family_suffix = gold_family_id.split("-", 1)[1]
            source_family_id = f"{source_env_id}-{family_suffix}"
            source_family = self.task_registry.family(source_family_id)
            shuffled_skill_id = source_family.meta.latent_skill_id
            if shuffled_skill_id in gold_skill_ids:
                raise RuntimeError(
                    f"shuffled skill {shuffled_skill_id!r} overlaps gold annotations"
                )
            mappings.append((gold_skill_id, shuffled_skill_id))
        shuffled_skill_ids = [shuffled for _, shuffled in mappings]
        if len(shuffled_skill_ids) != len(set(shuffled_skill_ids)):
            raise RuntimeError(
                f"shuffled diagnostic task {task.task_id} produced duplicate skills"
            )

        views_root = self.runtime.run_root / "shuffled-skill-views"
        view_dir = views_root / runtime_basename
        view_dir.mkdir(parents=True, exist_ok=True)
        for child in list(view_dir.iterdir()):
            if child.is_symlink() or child.is_file():
                child.unlink()
            elif child.is_dir():
                shutil.rmtree(child)
            else:
                raise RuntimeError(f"unsupported object in shuffled view: {child}")

        copied: list[dict[str, Any]] = []
        for gold_skill_id, shuffled_skill_id in mappings:
            slug = skill_id_to_slug(shuffled_skill_id)
            source = self.runtime.library.active_dir / slug
            if not source.is_dir() or source.is_symlink():
                raise RuntimeError(
                    f"shuffled curated content for {shuffled_skill_id!r} is unavailable"
                )
            for path in source.rglob("*"):
                if path.is_symlink():
                    raise RuntimeError(
                        f"shuffled skill {shuffled_skill_id!r} contains a forbidden symlink"
                    )
            destination = view_dir / slug
            shutil.copytree(source, destination)
            digest = hashlib.sha256()
            for path in sorted(
                (item for item in destination.rglob("*") if item.is_file()),
                key=lambda item: item.relative_to(destination).as_posix(),
            ):
                relative = path.relative_to(destination).as_posix()
                digest.update(relative.encode("utf-8"))
                digest.update(b"\0")
                digest.update(path.read_bytes())
                digest.update(b"\0")
            copied.append(
                {
                    "gold_skill_id": gold_skill_id,
                    "skill_id": shuffled_skill_id,
                    "slug": slug,
                    "sha256": digest.hexdigest(),
                }
            )

        audit = {
            "schema_version": 1,
            "condition": "shuffled_curated",
            "task_id": task.task_id,
            "runtime_basename": runtime_basename,
            "role": task.role,
            "gold_skill_ids": gold_skill_ids,
            "shuffled_skill_ids": shuffled_skill_ids,
            "source_environment_id": source_env_id,
            "skills": copied,
            "library_hash": self.runtime.library.compute_hash(),
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        audit_path = views_root / f"{runtime_basename}.audit.json"
        audit_path.write_text(
            json.dumps(audit, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
        self.runtime.event_store.record(
            "shuffled_skill_view_staged",
            {
                "task_id": task.task_id,
                "gold_skill_ids": gold_skill_ids,
                "shuffled_skill_ids": shuffled_skill_ids,
                "source_environment_id": source_env_id,
                "library_hash": audit["library_hash"],
            },
        )

    async def _create_zero_shot_skill(self, task: Any) -> None:
        """Self-Gen-Zero-Shot: ask the evolver to write a skill from family
        label *before* any execution trace exists."""
        family_meta = self.task_registry.family(task.family_id).meta
        content = await self.runtime.evolver.zero_shot_create(
            family_id=task.family_id,
            latent_skill_id=task.latent_skill_id,
            family_meta=family_meta,
        )
        self.runtime.library.create_skill(
            skill_id=task.latent_skill_id,
            content=content,
            source="zero_shot",
            family_id=task.family_id,
            created_from_task=task.task_id,
        )
        self.runtime.event_store.record(
            "zero_shot_created",
            {
                "family_id": task.family_id,
                "task_id": task.task_id,
                "latent_skill_id": task.latent_skill_id,
            },
        )

    def _assert_freeze_invariant(self, task: Any) -> None:
        """Hard assert: library hash never changes during T4-T6.

        Engineering Design §0.2 invariant 4. If this ever raises in
        production, treat the run's data as invalid -- something modified
        the library inside the eval block.
        """
        if self.runtime.freeze_ctrl.frozen:
            current = self.runtime.library.compute_hash()
            expected = self.runtime.freeze_ctrl.frozen_hash
            if current != expected:
                raise AssertionError(
                    f"Library hash changed during eval block at task "
                    f"{task.task_id!r}: got {current!r} expected {expected!r}"
                )


__all__ = ["SkillEvolBenchHooks"]
