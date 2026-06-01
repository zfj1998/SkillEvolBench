"""``ChainEvolution`` -- single-candidate linear revision (Part 7 §7.2).

The default strategy. Three branches:

* T1 + ``allow_self_gen_induction`` and no seed yet -> ``induce_skill`` and
  return :class:`ApplyPatch`.
* T2/T3 + ``_should_revise`` is True -> ``evolver.propose(mode=<chain mode>)``
  -> :class:`ApplyPatch`. Default mode is ``free_form`` (LLM may add
  scripts/references/assets when the trace shows they help). Override via
  ``StrategyConfig.candidate_modes`` in yaml.
* Otherwise -> :class:`NoOp` with a documented reason.

Failures from :class:`SkillAuthor` (already with internal fallback chain)
become :class:`NoOp` with the failure type encoded in the reason -- the
hook records them as ``noop_decision`` events.
"""

from __future__ import annotations

import logging

from skillevolbench.components.skill_author import PatchGenerationFailure
from skillevolbench.strategies.base import (
    ApplyPatch,
    EvolutionContext,
    EvolutionDecision,
    EvolutionStrategy,
    NoOp,
)


_LOG = logging.getLogger(__name__)


class ChainEvolution(EvolutionStrategy):
    name: str = "chain"

    def _decide_impl(self, ctx: EvolutionContext) -> EvolutionDecision:
        role = self._role_value(ctx)

        # T1: induce iff Self-Gen baseline AND no seed yet. For curated /
        # zero-shot baselines (which already have a v0 in the library at T1)
        # this short-circuits and we fall through to the revision path so a
        # canonical-task failure can still trigger a revise on v0.
        if role == "canonical" and self._should_induce(ctx):
            return self._induce_or_noop(ctx)

        # T1 (with seed) / T2 / T3: revision on failure
        if not self._should_revise(ctx):
            return NoOp(reason=self._why_not_revising(ctx))

        # The "suggested target" is what the 3-tier priority points to --
        # we still surface this in the prompt as a hint (the retriever's
        # best guess at what to revise).
        suggested_target_skill_ids = self._select_target_skills(ctx)
        if not suggested_target_skill_ids:
            return NoOp(reason="no_target_skills_to_revise")

        # But pass ALL family skills to propose() -- the LLM then sees
        # the whole family's library and can decide to revise the
        # suggested target, revise a different family skill, or create
        # a new sibling. Without this, the LLM was hard-constrained to
        # only the retriever's pick and could not consolidate across
        # sibling skills or fix a wrong target.
        all_family_skill_ids = self._all_family_skill_ids(ctx)
        # Defensive: ensure the suggested target is in the list (it may
        # already be there from skills_in_family; this dedupe + ordering
        # keeps the suggested first for the prompt's "← suggested" marker).
        target_skill_ids = list(dict.fromkeys(
            suggested_target_skill_ids + all_family_skill_ids
        ))

        # Cumulative trace: T_t sees T_1...T_t together so revisions can
        # reflect across the family's full episodic history (not just the
        # most recent trial). Helper returns a single compacted-shaped
        # object whose .text concatenates all prior learning-block
        # trajectories with per-trial headers.
        cumulative = self._build_cumulative_trace(ctx)

        # Chain config guarantees exactly one candidate_mode (validated in
        # StrategyConfig._check_strategy_invariants). Honour it; the
        # in-code fallback is ``free_form`` to match StrategyConfig's
        # field default and stay consistent with the comprehensive +
        # adversarial mindset baked into the system prompt.
        mode = (self.config.candidate_modes or ["free_form"])[0]
        try:
            patch = self.evolver.propose(
                library=self.library,
                compacted=cumulative,
                outcome=ctx.outcome,
                target_skill_ids=target_skill_ids,
                mode=mode,
                suggested_target_skill_ids=suggested_target_skill_ids,
            )
        except PatchGenerationFailure as exc:
            self.event_store.record(
                "candidate_failed",
                {
                    "task_id": ctx.task.task_id,
                    "strategy": self.name,
                    "error": str(exc)[:200],
                },
            )
            return NoOp(reason=f"patch_generation_failed:{type(exc).__name__}")

        self.event_store.record_patch_proposed(patch, self.name)
        return ApplyPatch(patch=patch)

    # ------------------------------------------------------------------

    def _why_not_revising(self, ctx: EvolutionContext) -> str:
        """Render a human-readable reason for the NoOp event."""
        if not ctx.baseline.allow_revision:
            return "baseline_does_not_allow_revision"
        role = self._role_value(ctx)
        if role not in {"canonical", "enriched", "variant"}:
            return f"role_not_revisable:{role}"
        if role == "canonical" and not ctx.library.has_seed_for(ctx.task.family_id):
            return "canonical_revision_needs_existing_seed"
        trigger = getattr(ctx.baseline, "revision_trigger", "never")
        if trigger == "never":
            return "revision_trigger_never"
        if trigger == "fail_only" and ctx.outcome.verifier_passed:
            return "trigger_fail_only_but_passed"
        return "no_revise_for_unknown_reason"


__all__ = ["ChainEvolution"]
