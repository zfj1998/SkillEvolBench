"""Baseline configuration schema.

Models yaml files in ``configs/baselines/`` as strict ``BaselineConfig``
objects. Each yaml is a flat capability-flag catalog; the combination of
flags defines a baseline such as No-Skill, Raw-Trajectory-RAG, or
Curated-with-Revision.

Cross-field invariants are enforced via ``@model_validator``; loading a yaml
that violates them fails immediately rather than silently producing
inconsistent runtime behavior. The schema enforces invariants that are statically deducible from yaml;
runtime-only invariants remain in ``BaselineRuntime.build``.
"""

from __future__ import annotations

from enum import Enum
from pathlib import Path
from typing import Any, Literal

import yaml
from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------


class Track(str, Enum):
    """Which experimental track a baseline belongs to.

    The track groups baselines and enforces protocol-specific invariants.
    """

    NONE = "none"  # No-Skill (lower bound)
    CONTROL = "control"  # Raw-Trajectory-RAG / History-Context-Control
    PATH_A = "path-a"  # Self-Gen-* (self-generated track)
    PATH_B = "path-b"  # Curated-* (curated revision track)


class FeedbackLevel(str, Enum):
    """How rich the failure-feedback signal is on T2/T3 fail."""

    NONE = "none"  # no feedback consumed
    BINARY = "binary"  # only pass/fail
    RICH = "rich"  # full ctrf-equivalent: failed test ids + messages
    PROCESS = "process"  # rich + trajectory step-level annotations


SkillInit = Literal["empty", "curated", "zero_shot"]
RevisionTrigger = Literal["never", "fail_only", "always"]
DefaultStrategy = Literal["none", "chain", "chain_tier3"]

# Library lifetime: how long does the skill library persist?
#
# - "global"      -- one library shared across all 6 environments. Skills
#                    induced/curated in E1 are still in the library when
#                    E2 starts. Enables cross-env transfer + composition
#                    metrics, but introduces retrieval interference (an
#                    E5 task may retrieve an E1 skill).
# - "environment" -- library is wiped at every env transition (just before
#                    the first task of the next env). Each env starts with
#                    only its own ``skill_init`` seeds. Mirrors SkillFlow's
#                    "family reset" design (Paper §2.4) but at env
#                    granularity -- within an env, the 5 latent skill
#                    families still share one library and accumulate
#                    revisions normally.
LibraryScope = Literal["global", "environment"]
SkillUpdateSource = Literal["host_skill_author", "same_agent_session"]


# ---------------------------------------------------------------------------
# Schema
# ---------------------------------------------------------------------------


class BaselineConfig(BaseModel):
    """One row of the Main Performance Table.

    The capability flags are deliberately a flat namespace (rather than nested
    sections) so that:

    1. ablations can flip a single flag and inherit everything else from a
       reference baseline yaml without touching nested schemas, and
    2. ``@model_validator`` rules can be expressed as predicates over the
       whole flag set.

    See ``configs/baselines/*.yaml`` for canonical and optional presets.
    """

    model_config = ConfigDict(use_enum_values=True, frozen=False)

    # ===== Identity =====
    name: str = Field(..., description="Unique baseline name (matches yaml stem)")
    description: str = Field(
        ..., description="One-sentence description for tables/plots"
    )
    track: Track

    # ===== Skill source =====
    skill_init: SkillInit = "empty"
    allow_self_gen_induction: bool = False  # T1 induce skill from execution trace
    allow_zero_shot_creation: bool = False  # T1-pre induce from family label only
    allow_curated_inject: bool = False  # inject curated v0 on family arrival

    # ===== Skill mutation permissions =====
    allow_revision: bool = False
    allow_retirement: bool = False
    allow_quarantine: bool = False
    allow_applicability_narrow: bool = False
    allow_rollback: bool = False

    # ===== Memory channels =====
    use_skill_library: bool = False
    use_trajectory_rag: bool = False
    use_history_context: bool = False
    use_feedback_memory: bool = False

    # ===== Library lifetime =====
    # Default is ``environment``: each env has its own LibraryStore at
    # library/<env_id>/ with own git repo + manifest, lazy-init by
    # ``switch_env`` on the env's first task. Cross-env retrieval
    # interference is impossible by construction -- an E1 task's
    # retriever only sees E1's skills. Mirrors SkillFlow's per-group
    # physical isolation, but at env granularity (within an env, the 5
    # latent-skill families share one library).
    #
    # Override to ``global`` only when you specifically want a single
    # library shared across all 6 envs -- e.g. the
    # ``curated_with_revision_always_global_scope`` ablation which
    # quantifies "how much SR drops when cross-env interference is let
    # in". ReplayStore / trajectories are unaffected by either choice.
    library_scope: LibraryScope = "environment"

    # ===== Memory parameters =====
    history_context_max_tokens: int = Field(default=8000, ge=0)
    trajectory_retrieval_k: int = Field(default=3, ge=0)
    skill_retrieval_k: int = Field(default=8, ge=0)

    # ===== Retriever choice =====
    # "embedding" -- dense embedding retriever (separate model). Fast,
    #                deterministic, but can't reason about task semantics.
    # "llm_self" (default) -- ask the agent's own LLM (baseline.model_name)
    #                to pick top-k. Adds one LLM call per task; matches
    #                the agent's own decision boundary about what's
    #                relevant. Non-deterministic but more accurate.
    # "oracle" -- T6 oracle ablation; returns required_skills verbatim.
    retriever_type: Literal["embedding", "llm_self", "oracle"] = "llm_self"

    # Soft family-aware retrieval. When > 0, EmbeddingRetriever adds this
    # value to the cosine similarity of any skill whose family_id matches
    # the current task's family. Effect: same-family skill is almost
    # guaranteed to top-k, but cross-family is still allowed if its raw
    # score is much higher (realistic). T6 (composition) is exempt --
    # composition tasks need cross-family retrieval, so the boost is
    # disabled there regardless of this value.
    #   0.0  : current behaviour (no boost; pure cosine)
    #   0.5  : recommended soft prior; flips ranks unless cross-family is
    #          ~0.5 cosine clearer than the same-family alternative
    #   1.0+ : effectively a hard same-family filter for T1-T5
    retrieval_family_boost: float = Field(default=0.0, ge=0.0)

    # Phase-aware retrieval scope (Scheme B; default ON). When True, the
    # EmbeddingRetriever HARD-FILTERS the candidate pool by role:
    #
    #   T1-T3 (learning):  only same-family skills are returned
    #     -- the agent's "skill" at learning time is the family's own
    #        induced/curated skill (and any sibling created by a CREATE
    #        revision); cross-family skills cannot help T1-T3 of a
    #        single-skill family.
    #
    #   T4-T6 (eval):      only same-env skills are returned
    #     -- benchmark spec confirms ALL 30 T6 tasks require_skills stay
    #        within the same env, so cross-env skills in retrieval are
    #        pure noise.
    #
    # When False, falls back to legacy "global cosine over full library"
    # behaviour (matches what canonical baselines did historically).
    # Use the *_global_retrieval ablation to opt out and measure the
    # cross-env transfer effect.
    retrieval_phase_aware: bool = True

    # Hard rule for revision target selection during T1-T3 learning: only
    # skills belonging to the current task's family may be revised. Without
    # this guard, an agent that incidentally references a cross-family
    # skill in its trajectory (e.g. ``ls /skills/`` pulling in unrelated
    # slugs) causes that cross-family skill to be picked as the patch
    # target -- corrupting it with evidence from a task that has nothing
    # to do with it. T6 (composition / eval) is unaffected because eval
    # tasks never reach the revision path. Default True.
    enforce_same_family_target: bool = True

    # Dual-T6 retrieval evaluation. When True, every T6 (composition) task
    # is run TWICE in the same run:
    #   1. PRIMARY trial   -- uses the baseline's normal retriever; this is
    #                          the trial that contributes to evaluation_sr
    #                          and t6_composition_rate (consistent with
    #                          non-dual baselines).
    #   2. SHADOW trial    -- uses OracleRetriever (required_skills);
    #                          contributes to t6_oracle_pass_rate and the
    #                          paired uplift metric. Library is frozen
    #                          (T4-T6 invariant) so both trials see the
    #                          identical library state -- the resulting
    #                          delta is a clean retrieval-only effect.
    # Adds 5 extra T6 trials per env (30 across the 6-env run).
    # Shadow trials skip strategy.decide() and lifecycle entirely.
    dual_t6_retrieval: bool = False

    # ===== Within-env replay =====
    # After each env's 30 tasks finish (15 learning + 15 eval, library now
    # at its final post-evolution state for that env), replay the SAME 30
    # tasks against the FROZEN library. Each replay trial gets a fresh
    # docker container + agent run; the library is locked so revision /
    # induction never fires. Used to measure "within-env evolution lift":
    #   replay_pass_rate(T_t) - original_pass_rate(T_t)
    #   = how much the library's evolution actually helped on the SAME
    #     tasks the library was built from.
    # Pairs cleanly with library_scope="environment" (default): the env's
    # post-evolution library is what's mounted during replay, so the
    # comparison stays within a single isolated environment.
    # Cost: 1.5x compute per env (45 trials instead of 30) when
    # ``replay_eval=False`` (default), or 2x (60 trials) when also
    # replaying eval. Default ON because evolution-quality measurement
    # is the primary signal of this benchmark; runs that don't care
    # can opt out via ``within_env_replay: false``.
    within_env_replay: bool = True

    # When replay is on, also replay T4-T6 (eval). DEFAULT False --
    # eval trials ran under the same frozen library state as the
    # replay would, so re-running them would just measure LLM
    # variance (no library lift to measure). Set True only for
    # ablations that want variance / post-eval-maintenance signals.
    replay_eval: bool = False

    # ===== Feedback =====
    feedback_level: FeedbackLevel = FeedbackLevel.NONE
    feedback_to_skill_text: bool = False  # rewrite skill content
    feedback_to_memory: bool = False  # store as feedback memory entry

    # ===== Lifecycle =====
    allow_post_eval_maintenance: bool = False

    # ===== Strategy =====
    default_strategy: DefaultStrategy = "none"
    revision_trigger: RevisionTrigger = "never"
    max_revisions_per_skill: int = Field(default=3, ge=0)

    # Who authors learning-time skill updates after T1-T3:
    #
    # - host_skill_author: the paper-compatible, independent host LLM call.
    # - same_agent_session: resume the task agent after verifier feedback and
    #   ask that exact session to emit a candidate patch.  The host still
    #   validates/applies it, so the agent never writes the shared library.
    skill_update_source: SkillUpdateSource = "host_skill_author"

    # Maximum number of verifier-backed solution attempts for each T1-T3
    # learning task.  Values above one are meaningful only for the
    # same-agent-session protocol: after a failed attempt, the exact OpenCode
    # session receives bounded verifier feedback, may repair /root/task, and
    # is graded again.  Passing stops the loop early.  T4-T6, replay, and
    # shadow trials always remain single-attempt observers.
    learning_max_attempts: int = Field(default=1, ge=1, le=5)

    # ===== Harbor agent =====
    harbor_agent_name: str = "claude-code"
    model_name: str = "anthropic/claude-opus-4-5"
    agent_kwargs: dict[str, Any] = Field(default_factory=dict)

    # -----------------------------------------------------------------
    # Field-level validators
    # -----------------------------------------------------------------

    @field_validator("name")
    @classmethod
    def _name_kebab_or_snake(cls, v: str) -> str:
        if not v or not all(c.isalnum() or c in "-_" for c in v):
            raise ValueError(f"name must be alphanumeric / '-' / '_', got {v!r}")
        return v

    # -----------------------------------------------------------------
    # Cross-field invariants (the part that earns its keep)
    # -----------------------------------------------------------------

    @model_validator(mode="after")
    def _check_protocol_invariants(self) -> "BaselineConfig":
        # ---- 1. No-Skill: all memory channels off, no induction/revision ----
        # Engineering Design §8.1: "No-Skill: 不给 skill / memory / trajectory /
        # history / feedback. 不做 induction / revision / retirement."
        if self.name == "no_skill":
            mem_flags = (
                self.use_skill_library,
                self.use_trajectory_rag,
                self.use_history_context,
                self.use_feedback_memory,
            )
            if any(mem_flags):
                raise ValueError(
                    "No-Skill baseline must have all use_*_library/rag/context/memory "
                    f"flags False; got {mem_flags}"
                )
            if (
                self.allow_self_gen_induction
                or self.allow_zero_shot_creation
                or self.allow_curated_inject
            ):
                raise ValueError("No-Skill must not allow any skill creation")
            if self.allow_revision or self.allow_retirement:
                raise ValueError("No-Skill must not allow revision or retirement")

        # ---- 2. Path-A track: never reads curated content ----
        # Engineering Design §0.2 invariant 3: "Path A 的 baseline 永远不读
        # benchmark/skills/<family>/skill.md"
        if self.track == Track.PATH_A:
            if self.skill_init == "curated":
                raise ValueError(
                    "Path-A baseline must not have skill_init='curated' "
                    "(would leak curated SKILL.md into a self-generated track)"
                )
            if self.allow_curated_inject:
                raise ValueError("Path-A baseline must have allow_curated_inject=False")

        # ---- 3. Path-B track: must inject curated v0 ----
        if self.track == Track.PATH_B:
            if self.skill_init != "curated":
                raise ValueError(
                    f"Path-B baseline expects skill_init='curated', got "
                    f"{self.skill_init!r}"
                )
            if not self.allow_curated_inject:
                raise ValueError("Path-B baseline must have allow_curated_inject=True")

        # ---- 4. Control track: skill library disabled ----
        # The point of Raw-Trajectory-RAG / History-Context-Control is to
        # measure how far raw memory goes WITHOUT skill abstraction.
        if self.track == Track.CONTROL:
            if self.use_skill_library:
                raise ValueError(
                    "Control baselines must have use_skill_library=False "
                    "(otherwise the baseline collapses into Path-A/B)"
                )
            if self.allow_revision or self.allow_retirement:
                raise ValueError(
                    "Control baselines must not allow skill revision/retirement"
                )

        # ---- 5. Skill-creation flag <-> skill_init mode ----
        if self.skill_init == "zero_shot" and not self.allow_zero_shot_creation:
            raise ValueError(
                "skill_init='zero_shot' requires allow_zero_shot_creation=True"
            )
        if self.allow_zero_shot_creation and self.skill_init != "zero_shot":
            raise ValueError(
                "allow_zero_shot_creation=True requires skill_init='zero_shot'"
            )
        if self.skill_init == "curated" and not self.allow_curated_inject:
            raise ValueError("skill_init='curated' requires allow_curated_inject=True")

        # ---- 6. Revision trigger consistency ----
        if self.revision_trigger != "never" and not self.allow_revision:
            raise ValueError(
                f"revision_trigger={self.revision_trigger!r} requires "
                "allow_revision=True"
            )
        if self.allow_revision and self.revision_trigger == "never":
            raise ValueError("allow_revision=True requires revision_trigger != 'never'")

        # ---- 7. Post-eval maintenance requires retirement OR quarantine ----
        # Engineering Design §6.6 LifecycleMaintainer
        if self.allow_post_eval_maintenance:
            if not (self.allow_retirement or self.allow_quarantine):
                raise ValueError(
                    "allow_post_eval_maintenance=True requires at least one of "
                    "allow_retirement / allow_quarantine"
                )

        # ---- 8. Feedback memory consistency ----
        if self.feedback_to_memory and not self.use_feedback_memory:
            raise ValueError(
                "feedback_to_memory=True requires use_feedback_memory=True"
            )

        # ---- 9. Same-session reflection requires an audited resumable CLI ----
        # The AP adapters for OpenCode and Codex both retain the native session
        # transcript, explicitly resume that session, and fail closed when the
        # solve transcript is not an exact prefix of the post-verifier turn.
        # Other CLIs must not silently degrade "same session" into a fresh call.
        if self.skill_update_source == "same_agent_session":
            if self.harbor_agent_name not in {"opencode", "codex"}:
                raise ValueError(
                    "skill_update_source='same_agent_session' currently "
                    "requires harbor_agent_name='opencode' or 'codex'"
                )
            if not self.use_skill_library:
                raise ValueError(
                    "same-session skill updates require use_skill_library=True"
                )
            if not (self.allow_self_gen_induction or self.allow_revision):
                raise ValueError(
                    "same-session skill updates require induction or revision"
                )
            if self.allow_zero_shot_creation:
                raise ValueError(
                    "same-session skill updates are post-verifier; zero-shot "
                    "pre-task creation must use a separate setting"
                )
        elif self.learning_max_attempts != 1:
            raise ValueError(
                "learning_max_attempts > 1 requires "
                "skill_update_source='same_agent_session'"
            )

        # ---- 10. Strategy must be 'none' iff no revision/induction ----
        # A strategy only does work in the learning block (T1 induction +
        # T2/T3 revision). If both are off, the strategy will never be invoked.
        does_anything = self.allow_self_gen_induction or self.allow_revision
        if not does_anything and self.default_strategy != "none":
            raise ValueError(
                f"default_strategy={self.default_strategy!r} requires "
                "allow_self_gen_induction=True or allow_revision=True"
            )
        if does_anything and self.default_strategy == "none":
            raise ValueError(
                "induction/revision enabled but default_strategy='none' -- "
                "the strategy layer would be a no-op"
            )

        return self

    # -----------------------------------------------------------------
    # Loaders
    # -----------------------------------------------------------------

    @classmethod
    def from_yaml(cls, path: Path | str) -> "BaselineConfig":
        """Load a yaml file and validate against this schema."""
        path = Path(path)
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)


__all__ = [
    "Track",
    "FeedbackLevel",
    "LibraryScope",
    "SkillInit",
    "RevisionTrigger",
    "DefaultStrategy",
    "BaselineConfig",
]
