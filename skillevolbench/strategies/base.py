"""Strategy ABC + decision types.

Concrete strategies share:

* :class:`EvolutionDecision` family -- ``ApplyPatch | NoOp``
* :class:`EvolutionContext`        -- everything decide() needs in one bag
* :class:`EvolutionStrategy`       -- ABC with the **defense-in-depth**
                                       T4-T6 NoOp guard

The hook (Part 4) already skips ``strategy.decide()`` for eval-block roles
{context-shift, adversarial, composition}. The base class enforces the
same invariant a second time -- if a future code path ever forgets to
gate, the strategy still returns NoOp instead of mutating the library.
"""

from __future__ import annotations

import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Optional

from skillevolbench.schemas import (
    BaselineConfig,
    CompactedTrajectory,
    RetrievalResult,
    SkillPatch,
    TrialOutcome,
)


_LOG = logging.getLogger(__name__)


# Role values from task.toml [metadata]. Used by the protocol guard.
_LEARNING_ROLES = frozenset({"canonical", "enriched", "variant"})
_EVAL_ROLES = frozenset({"context-shift", "adversarial", "composition"})


def _skill_family_id(skill_id: str) -> str:
    """Latent skill ids look like ``E1-LS1.systematic-error-diagnosis`` --
    family is the part before the first ``.``. Returns ``""`` for malformed
    ids so the same-family filter degrades to a no-op rather than throwing.
    """
    if not skill_id or "." not in skill_id:
        return ""
    return skill_id.split(".", 1)[0]


# ---------------------------------------------------------------------------
# Decisions
# ---------------------------------------------------------------------------


@dataclass
class EvolutionDecision:
    """Marker base. Strategies return one of the three subclasses below."""


@dataclass
class ApplyPatch(EvolutionDecision):
    """Strategy proposes this patch. The hook routes via
    :class:`LibraryFreezeController.submit_patch`."""

    patch: SkillPatch


@dataclass
class NoOp(EvolutionDecision):
    """Strategy did nothing. Either the role doesn't trigger this strategy
    (T1 with no induction permitted) or the trigger fired but generation
    failed (rare; falls back from PatchGenerationFailure)."""

    reason: str


# ---------------------------------------------------------------------------
# Context
# ---------------------------------------------------------------------------


@dataclass
class EvolutionContext:
    """Bundle of inputs to :meth:`EvolutionStrategy.decide`.

    Constructed from the trial outcome, compacted trajectory, retrieval
    result, and library state; everything is ready for strategy code to use.
    """

    task: Any
    outcome: TrialOutcome
    compacted: CompactedTrajectory
    pre_retrieval: Optional[RetrievalResult]
    skills_actually_used: list[str]
    baseline: BaselineConfig
    replay_store: Any
    library: Any


# ---------------------------------------------------------------------------
# ABC
# ---------------------------------------------------------------------------


class EvolutionStrategy(ABC):
    """Abstract base for revision strategies (Chain / Null).

    Subclasses implement :meth:`_decide_impl`. The wrapping :meth:`decide`
    enforces the T4-T6 NoOp invariant.
    """

    name: str = "base"

    def __init__(
        self,
        *,
        evolver: Optional[Any],
        retriever: Optional[Any],
        library: Any,
        replay_store: Optional[Any],
        event_store: Any,
        config: Any,
    ) -> None:
        self.evolver = evolver
        self.retriever = retriever
        self.library = library
        self.replay_store = replay_store
        self.event_store = event_store
        self.config = config

    # ----- public API -----

    def decide(self, ctx: EvolutionContext) -> EvolutionDecision:
        """Public entry: enforces the T4-T6 NoOp invariant, then dispatches."""
        role = self._role_value(ctx)
        if role in _EVAL_ROLES:
            # Defense in depth: hook already skips strategies in eval blocks,
            # but if a future caller forgets, NoOp is the safe response.
            return NoOp(reason="frozen_evaluation_block")
        return self._decide_impl(ctx)

    @abstractmethod
    def _decide_impl(self, ctx: EvolutionContext) -> EvolutionDecision: ...

    # ----- shared helpers -----

    @staticmethod
    def _role_value(ctx: EvolutionContext) -> str:
        """Pull the wire-format role string ('canonical', 'enriched', ...)."""
        role = getattr(ctx.task, "role", "")
        if hasattr(role, "value"):  # TaskRole enum
            return str(role.value)
        return str(role)

    def _should_induce(self, ctx: EvolutionContext) -> bool:
        """Self-Gen-* baselines induce a skill at T1 if no seed exists."""
        if not ctx.baseline.allow_self_gen_induction:
            return False
        if self._role_value(ctx) != "canonical":
            return False
        return not ctx.library.has_seed_for(ctx.task.family_id)

    def _should_revise(self, ctx: EvolutionContext) -> bool:
        """Revision triggers on any learning-block role when configured.

        Canonical (T1) is included so curated / zero-shot baselines that
        start with a v0 in the library can also revise it on first-trial
        failure -- this trace is too valuable to throw away.
        Self-Gen baselines bypass this path because their canonical handler
        runs ``_should_induce`` first; only when that returns False (e.g. seed
        already exists) does control reach here.
        """
        if not ctx.baseline.allow_revision:
            return False
        role = self._role_value(ctx)
        if role not in {"canonical", "enriched", "variant"}:
            return False
        # Canonical revision requires an existing seed (else nothing to revise).
        if role == "canonical" and not ctx.library.has_seed_for(ctx.task.family_id):
            return False
        trigger = getattr(ctx.baseline, "revision_trigger", "never")
        if trigger == "never":
            return False
        if trigger == "fail_only" and ctx.outcome.verifier_passed:
            return False
        return True

    def _select_target_skills(self, ctx: EvolutionContext) -> list[str]:
        """Which skills should the patch target?

        Priority:
          1. skills the agent actually used in the trajectory (most specific)
          2. skills that were retrieved (next-most-specific)
          3. any active skill in the same family (fallback)
          4. nothing (caller -> NoOp)

        When ``baseline.enforce_same_family_target`` is True (default), the
        priority-1 and -2 candidates are filtered to skills whose family_id
        matches the current task's family. This prevents the failure mode
        where an agent's incidental cross-family reference (or a wrong
        retrieval result) ends up as the patch target -- which would
        corrupt an unrelated skill with evidence from this task.
        T6 (eval) never reaches this method, so composition logic is
        unaffected.
        """
        task_family = getattr(ctx.task, "family_id", None)
        enforce = getattr(ctx.baseline, "enforce_same_family_target", True)
        same_family = (
            (lambda sid: _skill_family_id(sid) == task_family)
            if enforce and task_family
            else (lambda sid: True)
        )

        if ctx.skills_actually_used:
            # Filter to skills that still exist in the library; agents
            # sometimes reference deleted ones.
            existing = [
                sid for sid in ctx.skills_actually_used
                if ctx.library.has_skill(sid)
            ] or list(ctx.skills_actually_used[:3])
            same_fam = [sid for sid in existing if same_family(sid)]
            if same_fam:
                return same_fam
            # All actually-used skills were cross-family -> drop them and
            # fall through to retrieval / family fallback below.
        if ctx.pre_retrieval and ctx.pre_retrieval.skills:
            retrieved = [s.skill_id for s in ctx.pre_retrieval.skills[:3]]
            same_fam = [sid for sid in retrieved if same_family(sid)]
            if same_fam:
                return same_fam
        family_skills = ctx.library.skills_in_family(ctx.task.family_id)
        if family_skills:
            return [family_skills[0].skill_id]
        return []

    def _all_family_skill_ids(self, ctx: EvolutionContext) -> list[str]:
        """Return ALL active skills in the current task's family.

        This is the second axis the revision LLM gets in its prompt:
        it sees every skill in the family (not just the
        ``_select_target_skills`` pick), with the suggested target
        marked. Lets the LLM decide to revise a different skill or
        create a sibling when the suggested target isn't the right
        edit point.

        Returns ``[]`` when the family has no active skills (e.g.
        induction failed at T1).
        """
        family_id = getattr(ctx.task, "family_id", None)
        if not family_id:
            return []
        return [e.skill_id for e in ctx.library.skills_in_family(family_id)]

    def _build_cumulative_trace(self, ctx: EvolutionContext) -> Any:
        """Concatenate the family's prior learning-block trajectories +
        the current trial's compacted trace into one ``CompactedTrajectory``-
        shaped object (anything with a ``.text`` attribute is fine).

        Reasoning: revision at T_t works better when the LLM sees the
        full episodic history (T_1, ..., T_t) rather than only T_t's
        trace. Each trial is delimited by a header so the LLM can map
        actions to the trial that produced them.

        Eval-block records (T4-T6) are excluded -- they're the
        evaluation, not the learning episodes. Records are ordered by
        timestamp so the chronology matches the family's actual sequence.
        """
        family_id = getattr(ctx.task, "family_id", None)
        current_task_id = getattr(ctx.task, "task_id", None)
        learning_roles = {"canonical", "enriched", "variant"}

        prior_records = []
        if ctx.replay_store is not None and family_id:
            prior_records = [
                r for r in ctx.replay_store.tasks_by_family(family_id)
                if r.task_id != current_task_id
                and getattr(r, "task_role", "") in learning_roles
            ]

        parts: list[str] = []
        for r in prior_records:
            verdict = "PASSED" if r.outcome.verifier_passed else "FAILED"
            reward = getattr(r.outcome, "reward", 0.0) or 0.0
            parts.append(
                f"## Past trial: {r.task_id} ({verdict}, reward={reward:.2f})"
            )
            text = (r.trajectory_compact or {}).get("text", "")
            parts.append(text or "(trajectory unavailable)")
            parts.append("")

        # Current trial last so the LLM treats it as the focal evidence.
        cur_outcome = ctx.outcome
        cur_verdict = "PASSED" if cur_outcome.verifier_passed else "FAILED"
        cur_reward = getattr(cur_outcome, "reward", 0.0) or 0.0
        parts.append(
            f"## Current trial: {current_task_id} "
            f"({cur_verdict}, reward={cur_reward:.2f})"
        )
        parts.append(getattr(ctx.compacted, "text", "") or "(no trace)")

        # Wrap in a SimpleNamespace so propose() can read .text.
        # Real CompactedTrajectory not used here -- we don't need
        # n_events / n_tokens / raw_path for the revision input.
        from types import SimpleNamespace
        return SimpleNamespace(text="\n".join(parts))

    # ----- induction shared by strategies -----

    def _induce_or_noop(self, ctx: EvolutionContext) -> EvolutionDecision:
        """Common T1-induction path."""
        if not self._should_induce(ctx):
            return NoOp(reason="t1_no_induction_needed")
        try:
            patch = self.evolver.induce_skill(
                family_id=ctx.task.family_id,
                latent_skill_id=ctx.task.latent_skill_id,
                compacted=ctx.compacted,
                outcome=ctx.outcome,
            )
        except Exception as exc:  # PatchGenerationFailure or LLM error
            self.event_store.record(
                "induction_failed",
                {"task_id": ctx.task.task_id, "error": str(exc)[:200]},
            )
            return NoOp(reason=f"induction_failed:{type(exc).__name__}")
        self.event_store.record_patch_proposed(patch, self.name)
        return ApplyPatch(patch=patch)


__all__ = [
    "EvolutionDecision",
    "ApplyPatch",
    "NoOp",
    "EvolutionContext",
    "EvolutionStrategy",
]
