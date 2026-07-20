"""Trial-outcome / replay schemas (Part 5/6).

* ``TrialOutcome``      -- normalized per-trial result returned by Part 6
                            ``VerifierAdapter`` (parses the verifier-output
                            contract documented in PART1_STATIC_ASSETS.md §1.6).
* ``CompactedTrajectory`` -- summarized trajectory written into ReplayStore.
* ``ReplayRecord``      -- one row of ``replay.db`` + per-task json.

All fields are validated; the schemas are immutable enough that
``model_dump_json()`` output is what gets persisted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from skillevolbench.schemas.retrieval import RetrievalResult


# ---------------------------------------------------------------------------
# Verifier outputs
# ---------------------------------------------------------------------------


class FailedTest(BaseModel):
    """One failed test row pulled from outcome_report.json / process_report.json."""

    name: str
    message: str = ""
    trace: str = ""
    group: str = "outcome"   # "outcome" | "process"


class RubricDimension(BaseModel):
    """One row of ``score_report.json:dimensions``."""

    name: str
    weight: float = 0.0
    tests_matched: int = 0
    tests_passed: int = 0
    ratio: float = 0.0
    score: float = 0.0
    scoring: str = "proportional"


class TrialOutcome(BaseModel):
    """Normalized parse of ``/logs/verifier/*`` for one trial.

    The contract that produces this is documented in
    ``docs/PART1_STATIC_ASSETS.md`` §1.6. Part 6's ``VerifierAdapter``
    translates raw files -> this object.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    verifier_passed: bool = False
    reward: float = 0.0          # canonical reward.txt value, in [0, 1]
    max_score: float = 100.0
    normalized_score: float = 0.0

    # Outcome / process split (Part 1 §1.6):
    outcome_passed: Optional[bool] = None
    process_passed: Optional[bool] = None

    failed_tests: list[FailedTest] = Field(default_factory=list)
    failure_summary: str = ""
    rubric_dimensions: list[RubricDimension] = Field(default_factory=list)

    trial_dir: Optional[Path] = None     # Harbor trial directory
    trajectory_path: Optional[Path] = None

    # Agent-side cost (parsed from trajectory.json final_metrics by
    # VerifierAdapter). Host-side cost (SkillAuthor / Judge) is tracked
    # per-LiteLLMClient and aggregated separately in CostReport.
    n_input_tokens: int = 0
    n_output_tokens: int = 0
    n_cache_tokens: int = 0
    cost_usd: float = 0.0
    # Where did cost_usd come from?
    #   "agent_reported"        -- final_metrics.total_cost_usd was non-None
    #   "computed_from_tokens"  -- we derived it via the price table
    #   "unknown"               -- model not in price table AND no agent-reported cost
    #   ""                      -- no token info at all (e.g. trial_result is None)
    cost_source: str = ""


# ---------------------------------------------------------------------------
# Trajectory compaction
# ---------------------------------------------------------------------------


class CompactedTrajectory(BaseModel):
    """A token-budget-friendly summary of an agent trajectory.

    Compaction strategy lives in Part 6 ``TrajectoryCompactor``. The result
    is what gets stored in ReplayStore + injected into
    SkillAuthor / RGPE judge prompts.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    n_events: int = 0
    text: str = ""                # the actual compacted summary
    n_tokens: int = 0
    skills_referenced: list[str] = Field(default_factory=list)
    raw_path: Optional[Path] = None

    def to_dict(self) -> dict[str, Any]:
        """Plain dict for json serialization (used by ReplayRecord)."""
        return self.model_dump(mode="json")


# ---------------------------------------------------------------------------
# Replay record
# ---------------------------------------------------------------------------


class ReplayRecord(BaseModel):
    """One row of ``replay.db.replay_records`` + per-task json file.

    Constructed in :py:meth:`SkillEvolBenchHooks._on_trial_ended_sync`.
    Persisted by ``ReplayStore.persist``.
    """

    model_config = ConfigDict(arbitrary_types_allowed=True)

    task_id: str
    family_id: str
    env_id: str
    task_role: str            # "canonical" | "enriched" | ... (string for sqlite)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    library_hash_pre: Optional[str] = None
    library_hash_post: Optional[str] = None

    outcome: TrialOutcome
    retrieval: Optional[RetrievalResult] = None
    skills_actually_used: list[str] = Field(default_factory=list)
    # ``trajectory_compact`` is the RICH compaction (reasoning preserved,
    # full obs, large per-trial budget) -- consumed by SkillAuthor's
    # cumulative-trace input for revision/induction.
    trajectory_compact: dict[str, Any] = Field(default_factory=dict)
    # ``trajectory_compact_rough`` is the ROUGH compaction (reasoning
    # dropped, brief obs, small budget) -- consumed by raw_trajectory_rag's
    # TrajectoryRetriever as agent-prompt input. Kept separate so that
    # the "raw episodic experience" baseline does NOT silently inherit
    # the abstraction-friendly preprocessing applied for SkillAuthor.
    # Optional: legacy records may be missing this; consumers should
    # fall back to ``trajectory_compact`` when absent.
    trajectory_compact_rough: dict[str, Any] = Field(default_factory=dict)

    # Present for the same-agent-session protocol. This is deliberately a
    # plain audit dict so legacy records and paper-compatible baselines remain
    # schema-compatible. Typical keys: status, mode, session_id, patch_id,
    # candidate_path, and reason.
    reflection: dict[str, Any] = Field(default_factory=dict)

    # Dual-T6 evaluation marker. ``"primary"`` is the standard trial whose
    # outcome feeds evaluation_sr / t6_composition_rate. ``"shadow_oracle"``
    # is the second trial of the same T6 task, run with OracleRetriever
    # for a paired retrieval-only comparison; it does not contribute to
    # the headline metrics (filtered out) but feeds the new
    # ``t6_oracle_pass_rate`` / ``t6_oracle_uplift`` metrics.
    # Only T6 tasks of ``baseline.dual_t6_retrieval=True`` runs ever set
    # this to anything other than ``"primary"``.
    replay_mode: str = "primary"

    @field_validator("task_role")
    @classmethod
    def _check_role(cls, v: str) -> str:
        ok = {"canonical", "enriched", "variant", "context-shift",
              "adversarial", "composition"}
        if v not in ok:
            raise ValueError(f"task_role must be one of {ok}, got {v!r}")
        return v


__all__ = [
    "FailedTest",
    "RubricDimension",
    "TrialOutcome",
    "CompactedTrajectory",
    "ReplayRecord",
]
