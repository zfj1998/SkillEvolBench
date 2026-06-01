"""Baseline runtime + policy registry.

* :class:`BaselineRuntime` -- the dependency-injection container that
                              satisfies ``RuntimeProtocol``.
* :func:`load_baseline`     -- load a single baseline yaml by name.
* :data:`CANONICAL_BASELINES` -- canonical baseline names.
"""

from skillevolbench.baselines.policy import (
    CANONICAL_BASELINES,
    baseline_yaml_path,
    is_canonical,
    load_baseline,
    load_canonical_baselines,
)
from skillevolbench.baselines.runtime import BaselineRuntime


__all__ = [
    "BaselineRuntime",
    "CANONICAL_BASELINES",
    "baseline_yaml_path",
    "is_canonical",
    "load_baseline",
    "load_canonical_baselines",
]
