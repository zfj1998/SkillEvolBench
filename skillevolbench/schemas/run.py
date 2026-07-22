"""Run-level configuration schema.

Bundles BaselineConfig + StrategyConfig + per-run knobs (run_id, order_seed,
workspace, Harbor orchestrator type, LLM endpoint) into a single ``RunConfig``
that is the unique input to ``LifelongRunner.run()``.

Two auxiliary loaders also live here:

* ``EnvOrders.from_yaml(...)`` -> reads ``configs/env_orders.yaml``
                                    and validates the three seeds A/B/C.
* ``LLMDefaults.from_yaml(...)`` -> reads ``configs/llm.yaml`` and supplies
                                    fallback model names + endpoint.

Hard invariants enforced here:

* ``harbor_n_concurrent_trials == 1`` (lifelong protocol -- §4.3 of design).
* ``order_seed`` must be one of A / B / C.
* ``baseline.default_strategy`` must agree with ``strategy.name`` (or be
  ``"none"`` when the baseline doesn't use a strategy).
"""

from __future__ import annotations

import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal, Optional

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from skillevolbench.schemas.baseline import BaselineConfig
from skillevolbench.schemas.strategy import StrategyConfig


HarborOrchestratorType = Literal["local", "daytona", "modal", "e2b"]
OrderSeed = Literal["A", "B", "C"]
EnvironmentId = Literal["E1", "E2", "E3", "E4", "E5", "E6"]


# ---------------------------------------------------------------------------
# Auxiliary configs
# ---------------------------------------------------------------------------


class EnvOrders(BaseModel):
    """Three environment orderings used by the Order-Sensitivity ablation."""

    seed_a: list[str] = Field(..., min_length=6, max_length=6)
    seed_b: list[str] = Field(..., min_length=6, max_length=6)
    seed_c: list[str] = Field(..., min_length=6, max_length=6)

    @field_validator("seed_a", "seed_b", "seed_c")
    @classmethod
    def _check_envs(cls, v: list[str]) -> list[str]:
        expected = {f"E{i}" for i in range(1, 7)}
        if set(v) != expected:
            raise ValueError(f"each seed must be a permutation of E1..E6; got {v}")
        if len(v) != len(set(v)):
            raise ValueError(f"seed has duplicates: {v}")
        return v

    @classmethod
    def from_yaml(cls, path: Path | str) -> "EnvOrders":
        path = Path(path)
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)

    def for_seed(self, seed: OrderSeed) -> list[str]:
        return {"A": self.seed_a, "B": self.seed_b, "C": self.seed_c}[seed]


class LLMDefaults(BaseModel):
    """Default LLM endpoint config from ``configs/llm.yaml``."""

    api_base: Optional[str] = None
    api_key_env_var: str = "ANTHROPIC_API_KEY"

    default_agent_model: str = "anthropic/claude-opus-4-5"
    default_author_model: str = "anthropic/claude-opus-4-5"
    default_judge_model: str = "anthropic/claude-haiku-4-5"
    default_embed_model: str = "Qwen/Qwen3-Embedding-4B"

    author_temperature: float = 0.2
    author_max_tokens: int = 16384
    judge_temperature: float = 0.0
    judge_max_tokens: int = 1024

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_patch_fields(cls, data):
        """Accept pre-rename configs that used patch_* for author settings."""
        if not isinstance(data, dict):
            return data
        upgraded = dict(data)
        legacy_map = {
            "default_patch_model": "default_author_model",
            "patch_temperature": "author_temperature",
            "patch_max_tokens": "author_max_tokens",
        }
        for old_key, new_key in legacy_map.items():
            if old_key in upgraded and new_key not in upgraded:
                upgraded[new_key] = upgraded[old_key]
        return upgraded

    @classmethod
    def from_yaml(cls, path: Path | str) -> "LLMDefaults":
        path = Path(path)
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)


# ---------------------------------------------------------------------------
# RunConfig
# ---------------------------------------------------------------------------


class RunConfig(BaseModel):
    """Top-level config of one ``LifelongRunner.run()`` invocation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    # ===== Identification =====
    run_id: str = Field(..., description="Unique within workspace_root")

    # ===== Asset paths (allow override for fixtures / mini benchmarks) =====
    benchmark_skills_root: Path = Path("benchmark/skills")
    benchmark_tasks_root: Path = Path("benchmark/tasks")

    # ===== Configs =====
    baseline: BaselineConfig
    strategy: StrategyConfig

    # ===== Run params =====
    order_seed: OrderSeed = "A"
    # Run one self-contained environment episode instead of the six-environment
    # benchmark. This is the AP execution unit: the selected environment keeps
    # all of its trials in one process so the skill library remains stateful.
    environment_id: Optional[EnvironmentId] = None
    # Explicit six-primary-trial infrastructure smoke for one skill family.
    # This is deliberately non-canonical and therefore never scoreable.  It is
    # a separate selector (rather than max_tasks=6) because the canonical
    # environment order's first six tasks are T1-T3 from two families, not one
    # family's T1-T6 sequence.
    family_smoke_id: Optional[str] = None
    # Non-canonical diagnostic slice containing the five families' T4-T6
    # tasks (15 primaries) for one environment.  This is used for matched
    # no-skill versus curated-oracle solvability controls and is never a
    # benchmark score.
    evaluation_only_t4_t6: bool = False
    # Replace the normal whole-library skill mounts with a per-trial view that
    # contains exactly primary_skill for T4/T5 and required_skills for T6.
    # Only valid for the curated evaluation-only diagnostic above.
    oracle_skill_view: bool = False
    workspace_root: Path = Path("workspace/runs")

    # ===== Execution =====
    harbor_orchestrator_type: HarborOrchestratorType = "local"
    # Lifelong protocol hard requirement: tasks must run sequentially so the
    # global skill library is consistent across trials. Any value other than 1
    # breaks the score-before-maintain rule.
    harbor_n_concurrent_trials: int = Field(default=1, ge=1)
    # Runtime budget for slow model/tool loops.  This is orthogonal to the
    # benchmark's verifier-backed attempt count: it only changes how long one
    # agent phase may run.  AP uses a fixed value across compared models.
    harbor_agent_timeout_multiplier: float = Field(default=1.0, ge=1.0, le=8.0)

    # ===== LLM endpoints =====
    api_base: Optional[str] = None
    api_key_env_var: str = "ANTHROPIC_API_KEY"

    # ===== Execution mode =====
    dry_run: bool = False
    # Optional fixture knob: when set, truncate the scheduled task list to the
    # first N tasks and skip the strict full-benchmark order invariant. Public
    # launchers leave this as None.
    max_tasks: Optional[int] = Field(default=None, ge=1)

    # -----------------------------------------------------------------
    # Field validators
    # -----------------------------------------------------------------

    @field_validator("run_id")
    @classmethod
    def _check_run_id(cls, v: str) -> str:
        if not v or "/" in v or "\\" in v or v.startswith("."):
            raise ValueError(f"run_id must not contain path separators: {v!r}")
        if any(c.isspace() for c in v):
            raise ValueError(f"run_id must not contain whitespace: {v!r}")
        return v

    @field_validator("workspace_root")
    @classmethod
    def _resolve_workspace_root(cls, v: Path) -> Path:
        # Force absolute. Downstream `build_job_config` writes
        # `library_active_path` into Harbor's docker-compose mount source,
        # and Docker/Podman's bind-mount semantics require absolute paths
        # -- a relative source silently produces nested host paths
        # (e.g. `runtime/<task_id>/environment/workspace/runs/.../library/active`).
        return v.expanduser().resolve()

    @field_validator("family_smoke_id")
    @classmethod
    def _check_family_smoke_id(cls, v: Optional[str]) -> Optional[str]:
        if v is not None and not re.fullmatch(r"E[1-6]-LS[1-5]", v):
            raise ValueError(f"family_smoke_id must match E[1-6]-LS[1-5], got {v!r}")
        return v

    # -----------------------------------------------------------------
    # Cross-field invariants
    # -----------------------------------------------------------------

    @model_validator(mode="after")
    def _check_run_invariants(self) -> "RunConfig":
        # ---- 1. n_concurrent_trials must be 1 ----
        # Engineering Design §4.3: hard requirement of the lifelong protocol.
        if self.harbor_n_concurrent_trials != 1:
            raise ValueError(
                f"harbor_n_concurrent_trials must be 1 for the lifelong "
                f"protocol; got {self.harbor_n_concurrent_trials}"
            )

        # An AP environment episode is semantically equivalent only for the
        # default environment-scoped protocol. A global library intentionally
        # transfers state across E1..E6 and must run as one full sequential
        # job instead of six isolated pods.
        if (
            self.environment_id is not None
            and self.baseline.use_skill_library
            and self.baseline.library_scope != "environment"
        ):
            raise ValueError(
                "environment_id cannot be combined with "
                f"library_scope={self.baseline.library_scope!r}; global-scope "
                "baselines must run all six environments in one process"
            )

        if self.family_smoke_id is not None:
            if self.environment_id is None:
                raise ValueError(
                    "family_smoke_id requires its environment_id so the "
                    "stateful library scope is explicit"
                )
            family_environment = self.family_smoke_id.split("-", 1)[0]
            if self.environment_id != family_environment:
                raise ValueError(
                    f"family_smoke_id {self.family_smoke_id!r} belongs to "
                    f"{family_environment}, not environment_id="
                    f"{self.environment_id!r}"
                )
            if self.max_tasks is not None:
                raise ValueError(
                    "family_smoke_id and max_tasks are mutually exclusive; "
                    "a family smoke has an explicit T1-T6 schedule"
                )
            if self.baseline.within_env_replay or self.baseline.replay_eval:
                raise ValueError(
                    "family_smoke_id requires within_env_replay=False and "
                    "replay_eval=False so the smoke contains exactly T1-T6"
                )

        if self.evaluation_only_t4_t6:
            if self.environment_id is None:
                raise ValueError(
                    "evaluation_only_t4_t6 requires environment_id"
                )
            if self.family_smoke_id is not None or self.max_tasks is not None:
                raise ValueError(
                    "evaluation_only_t4_t6 is mutually exclusive with "
                    "family_smoke_id and max_tasks"
                )
            if self.baseline.within_env_replay or self.baseline.replay_eval:
                raise ValueError(
                    "evaluation_only_t4_t6 requires within_env_replay=False "
                    "and replay_eval=False"
                )
            if self.baseline.dual_t6_retrieval:
                raise ValueError(
                    "evaluation_only_t4_t6 requires dual_t6_retrieval=False"
                )

        if self.oracle_skill_view:
            if not self.evaluation_only_t4_t6:
                raise ValueError(
                    "oracle_skill_view requires evaluation_only_t4_t6=True"
                )
            if (
                self.baseline.skill_init != "curated"
                or not self.baseline.allow_curated_inject
                or not self.baseline.use_skill_library
            ):
                raise ValueError(
                    "oracle_skill_view requires a curated skill-library baseline"
                )

        # ---- 2. baseline.default_strategy <-> strategy.name ----
        # The baseline's "default_strategy" lives in its yaml as a hint about
        # which strategy yaml is expected to be paired with it. RunConfig's
        # `strategy` overrides that, but if the baseline expects something
        # specific, we shouldn't silently mix.
        bl_default = self.baseline.default_strategy
        if bl_default != "none" and self.strategy.name != bl_default:
            raise ValueError(
                f"baseline {self.baseline.name!r} expects strategy "
                f"{bl_default!r} but RunConfig pairs it with strategy "
                f"{self.strategy.name!r}; explicit override is allowed but "
                "must be configured by changing baseline.default_strategy "
                "first (otherwise result attribution becomes ambiguous)."
            )
        if bl_default == "none" and self.strategy.name != "chain":
            # When the baseline declares it doesn't use a strategy (No-Skill,
            # Curated-Static, etc.) we still need to load *something* to have
            # a complete RunConfig. By convention the harness will pair these
            # baselines with a "no-op" strategy at the runtime layer (Part 8).
            # Here we only allow chain (whose name == 'chain') as the trivial
            # placeholder to keep the schema simple.
            raise ValueError(
                f"baseline {self.baseline.name!r} has default_strategy='none' "
                f"so it must be paired with the 'chain' placeholder strategy; "
                f"got {self.strategy.name!r}"
            )

        return self

    # -----------------------------------------------------------------
    # Helpers
    # -----------------------------------------------------------------

    @property
    def run_dir(self) -> Path:
        """Path under which all run artifacts live."""
        return self.workspace_root / self.run_id

    @property
    def api_key(self) -> Optional[str]:
        """Resolve the API key from the configured environment variable.

        Returns None if the env var is unset; downstream code should raise
        when it actually tries to call the LLM and the key is missing.
        """
        return os.environ.get(self.api_key_env_var)

    @classmethod
    def from_paths(
        cls,
        *,
        run_id: str,
        baseline_yaml: Path | str,
        strategy_yaml: Path | str,
        order_seed: OrderSeed = "A",
        environment_id: Optional[EnvironmentId] = None,
        family_smoke_id: Optional[str] = None,
        evaluation_only_t4_t6: bool = False,
        oracle_skill_view: bool = False,
        workspace_root: Path | str = "workspace/runs",
        api_base: Optional[str] = None,
        api_key_env_var: str = "ANTHROPIC_API_KEY",
        dry_run: bool = False,
        max_tasks: Optional[int] = None,
    ) -> "RunConfig":
        """Compose a RunConfig from yaml file paths."""
        baseline = BaselineConfig.from_yaml(baseline_yaml)
        strategy = StrategyConfig.from_yaml(strategy_yaml)
        return cls(
            run_id=run_id,
            baseline=baseline,
            strategy=strategy,
            order_seed=order_seed,
            environment_id=environment_id,
            family_smoke_id=family_smoke_id,
            evaluation_only_t4_t6=evaluation_only_t4_t6,
            oracle_skill_view=oracle_skill_view,
            workspace_root=Path(workspace_root),
            api_base=api_base,
            api_key_env_var=api_key_env_var,
            dry_run=dry_run,
            max_tasks=max_tasks,
        )

    @staticmethod
    def make_run_id(
        baseline_name: str,
        strategy_name: str,
        order_seed: str = "A",
        timestamp: Optional[datetime] = None,
    ) -> str:
        """Canonical run_id format used by every script in scripts/."""
        ts = (timestamp or datetime.now(timezone.utc)).strftime("%Y%m%d_%H%M")
        return f"{baseline_name}__{strategy_name}__seed{order_seed}__{ts}"


__all__ = [
    "HarborOrchestratorType",
    "OrderSeed",
    "EnvironmentId",
    "EnvOrders",
    "LLMDefaults",
    "RunConfig",
]
