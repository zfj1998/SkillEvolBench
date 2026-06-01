"""Canonical baseline registry.

The actual capability flags live in ``configs/baselines/<name>.yaml``; this
module is the single source of truth for which yaml files are part of the
canonical benchmark ladder. Optional ablation configs can live alongside the
canonical set and be loaded directly by name or path.
"""

from __future__ import annotations

from pathlib import Path
from typing import Final

from skillevolbench.schemas import BaselineConfig


# 6 canonical baselines = Main Performance Table rows.
# Active learners (rows 4 & 6) use ``revision_trigger=always`` -- every
# learning trial (T1-T3) triggers SkillAuthor.propose, success or failure.
# The propose() prompt is PASS-aware so passes get a "distill the
# successful trajectory" framing. fail_only variants are kept as
# ablations (selfgen_experience / curated_with_revision yamls).
#
# Removed from canonical: selfgen_full_lifecycle / curated_full_lifecycle
# (lifecycle retire/quarantine ablation deferred); the older
# selfgen_experience_feedback_* fail_only variants (replaced by
# selfgen_experience_always_feedback_* on the always trigger so the
# feedback ablation is on the same trigger as main).
CANONICAL_BASELINES: Final[tuple[str, ...]] = (
    # Lower bound
    "no_skill",
    # Control (memory without skill abstraction)
    "raw_trajectory_rag",
    # Path A: self-generated skill, static (induced once, frozen)
    "selfgen_zero_shot",
    # Path A: self-generated skill, dynamic (induce + always revise)
    "selfgen_experience_always",
    # Path B: human-curated skill, static (no revision)
    "curated_static",
    # Path B: human-curated skill, dynamic (curated v0 + always revise)
    "curated_with_revision_always",
)


def repo_root() -> Path:
    """Default repo root (the directory containing ``configs/``)."""
    here = Path(__file__).resolve().parent
    return here.parent.parent


def baseline_yaml_path(name: str, *, configs_root: Path | None = None) -> Path:
    """Resolve ``configs/baselines/<name>.yaml`` (overridable for tests)."""
    root = Path(configs_root) if configs_root else (repo_root() / "configs" / "baselines")
    return root / f"{name}.yaml"


def load_baseline(name: str, *, configs_root: Path | None = None) -> BaselineConfig:
    """Load and validate the named baseline from yaml."""
    return BaselineConfig.from_yaml(baseline_yaml_path(name, configs_root=configs_root))


def load_canonical_baselines(
    *, configs_root: Path | None = None
) -> dict[str, BaselineConfig]:
    """Load all canonical baselines into a dict keyed by name."""
    return {n: load_baseline(n, configs_root=configs_root) for n in CANONICAL_BASELINES}


def is_canonical(name: str) -> bool:
    """True iff ``name`` is one of the canonical baselines."""
    return name in CANONICAL_BASELINES


__all__ = [
    "CANONICAL_BASELINES",
    "baseline_yaml_path",
    "load_baseline",
    "load_canonical_baselines",
    "is_canonical",
]
