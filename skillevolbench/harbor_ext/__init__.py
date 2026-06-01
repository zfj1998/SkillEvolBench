"""Harbor integration layer (Part 4).

Three modules:

* :mod:`skillevolbench.harbor_ext.types`      -- ``RuntimeProtocol`` / typing
                                                  helpers. NO Harbor import.
* :mod:`skillevolbench.harbor_ext.hooks`      -- ``SkillEvolBenchHooks``.
                                                  NO Harbor import at module
                                                  load (TYPE_CHECKING only).
* :mod:`skillevolbench.harbor_ext.env`        -- ``GlobalLibraryEnvironment``.
                                                  HARD harbor import.
* :mod:`skillevolbench.harbor_ext.job_builder` -- ``build_job_config``.
                                                  HARD harbor import.

This ``__init__`` re-exports the always-importable pieces (types + hooks).
The Harbor-dependent pieces (``env`` + ``job_builder``) are NOT auto-imported
here -- callers must explicitly ``import skillevolbench.harbor_ext.env``,
which fails with a clean ``ImportError`` when the SDK is missing.

Rationale: this lets ``pytest tests/unit/`` and ``scripts/validate_assets.py``
run on developer machines that have not yet installed the Harbor SDK, while
still allowing ``LifelongRunner`` (Part 9) to fail loudly when Harbor is
required for an actual run.
"""

from skillevolbench.harbor_ext.types import (
    RuntimeProtocol,
    TaskRegistryProtocol,
    RuntimeBuilderProtocol,
    PromptBuilderProtocol,
)
from skillevolbench.harbor_ext.hooks import SkillEvolBenchHooks


def harbor_available() -> bool:
    """True iff the Harbor SDK can be imported. Cheap, idempotent."""
    try:
        import harbor  # noqa: F401
    except ImportError:
        return False
    return True


__all__ = [
    "RuntimeProtocol",
    "TaskRegistryProtocol",
    "RuntimeBuilderProtocol",
    "PromptBuilderProtocol",
    "SkillEvolBenchHooks",
    "harbor_available",
]
