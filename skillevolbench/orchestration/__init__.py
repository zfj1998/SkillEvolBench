"""Run-level orchestration.

Public entry:
    ``LifelongRunner`` -- validates assets/configs, builds BaselineRuntime,
    runs the Harbor job, finalizes snapshots, and writes the run report.
"""

from skillevolbench.orchestration.lifelong_runner import LifelongRunner

__all__ = [
    "LifelongRunner",
]
