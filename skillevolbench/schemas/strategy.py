"""Strategy configuration schema.

Models yaml files in ``configs/strategies/`` as strict Pydantic v2
``StrategyConfig`` objects.

A strategy decides how skill edits are proposed during T1-T3 learning roles.
Public strategies:

* ``chain``       -- one candidate, free-form revision
* ``chain_tier3`` -- one candidate that must include a Tier-3 support artifact
"""

from __future__ import annotations

from pathlib import Path
from typing import Literal

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


StrategyName = Literal["chain", "chain_tier3"]
CandidateMode = Literal[
    "minimal_edit",
    "scope_narrow",
    "refactor",
    "retire_replace",
    "free_form",
    "tier3_required",
]


class StrategyConfig(BaseModel):
    """One revision strategy loaded from ``configs/strategies/<name>.yaml``."""

    model_config = ConfigDict(use_enum_values=True)

    name: StrategyName = Field(..., description="chain | chain_tier3")

    n_candidates: int = Field(default=1, ge=1, le=16)
    candidate_modes: list[CandidateMode] = Field(default_factory=lambda: ["free_form"])

    author_model: str = "anthropic/claude-opus-4-5"
    author_temperature: float = Field(default=0.2, ge=0.0, le=2.0)
    author_max_tokens: int = Field(default=16384, ge=1)

    # Public strategies do not use a separate judge, but the fields remain so
    # older config files can still parse cleanly.
    judge_model: str = "anthropic/claude-haiku-4-5"
    judge_temperature: float = Field(default=0.0, ge=0.0, le=2.0)
    judge_max_tokens: int = Field(default=1024, ge=1)

    @model_validator(mode="before")
    @classmethod
    def _accept_legacy_patch_fields(cls, data):
        """Accept pre-rename configs that used patch_* for author settings."""
        if not isinstance(data, dict):
            return data
        upgraded = dict(data)
        legacy_map = {
            "patch_model": "author_model",
            "patch_temperature": "author_temperature",
            "patch_max_tokens": "author_max_tokens",
        }
        for old_key, new_key in legacy_map.items():
            if old_key in upgraded and new_key not in upgraded:
                upgraded[new_key] = upgraded[old_key]
        return upgraded

    @field_validator("candidate_modes")
    @classmethod
    def _modes_unique_nonempty(cls, v: list[str]) -> list[str]:
        if not v:
            raise ValueError("candidate_modes must not be empty")
        if len(set(v)) != len(v):
            raise ValueError(f"candidate_modes contains duplicates: {v}")
        return v

    @model_validator(mode="after")
    def _check_strategy_invariants(self) -> "StrategyConfig":
        if self.n_candidates != 1:
            raise ValueError(
                f"{self.name} strategy requires n_candidates=1, "
                f"got {self.n_candidates}"
            )
        if len(self.candidate_modes) != 1:
            raise ValueError(
                f"{self.name} strategy requires exactly one candidate_mode, "
                f"got {self.candidate_modes}"
            )
        return self

    @classmethod
    def from_yaml(cls, path: Path | str) -> "StrategyConfig":
        path = Path(path)
        with path.open() as fh:
            data = yaml.safe_load(fh) or {}
        return cls.model_validate(data)


__all__ = [
    "StrategyName",
    "CandidateMode",
    "StrategyConfig",
]
