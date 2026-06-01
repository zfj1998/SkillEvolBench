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
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from skillevolbench.schemas import TaskRole, TaskPhase

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
        if self.runtime.baseline.use_skill_library:
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
        if self.runtime.baseline.use_trajectory_rag and self.runtime.trajectory_retriever:
            trajectories = self.runtime.trajectory_retriever.retrieve(
                task=task, k=self.runtime.baseline.trajectory_retrieval_k,
            )
        history_context: str | None = None
        if self.runtime.baseline.use_history_context and self.runtime.history_retriever:
            history_context = self.runtime.history_retriever.build_context(
                task=task,
                max_tokens=self.runtime.baseline.history_context_max_tokens,
            )

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
            task_id=runtime_basename,                # <task_id>__oracle_shadow
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
            retrieved_trajectories=[],   # shadow does not see traj RAG
            history_context=None,        # shadow does not see history
            library_frozen=True,         # always frozen (we're at T6 eval)
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
            return
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
            return

        # 1. Parse verifier output (Part 6 VerifierAdapter).
        outcome = self.runtime.verifier_adapter.parse(event.result)

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
            outcome.trajectory_path, outcome=outcome,
        )
        compacted_rough = self.runtime.compactor_rough.compact(
            outcome.trajectory_path, outcome=outcome,
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
            ApplyPatch, NoOp, EvolutionContext,
        )

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
            self.runtime.freeze_ctrl.submit_patch(
                patch=decision.patch,
                strategy_name=self.runtime.strategy.name,
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
            target = n_families_in_env * 3   # 3 learning roles per family
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
                        getattr(self.runtime, "library_root",
                                self.runtime.run_root / "library") / prev_env
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
        path = Path(self.runtime.run_root) / ".." / ".." / ".." / (
            f"benchmark/tasks/{task.task_slug}/{task.harbor.instruction}"
        )
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
