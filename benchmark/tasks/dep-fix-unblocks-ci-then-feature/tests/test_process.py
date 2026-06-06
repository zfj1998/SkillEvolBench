"""Process verifier for E1-LS2-T4.

P1: Dependency conflict resolved (constraints-ci.txt updated)
P2: CSV export endpoint implemented
P3: Agent addressed both the hidden CI blocker and the PR feature
"""

import re
from pathlib import Path

TASK_DIR = Path(__file__).resolve().parents[1]
COPIED_TASK_ROOT = TASK_DIR / "project"
PROJECT = COPIED_TASK_ROOT / "project"


def _read(relpath):
    return (PROJECT / relpath).read_text()


def test_process_p1_constraints_updated():
    """constraints-ci.txt no longer pins numpy==1.24.0 or custom-ml-utils==0.3.0."""
    constraints = _read("constraints-ci.txt")
    assert "numpy==1.24.0" not in constraints, (
        "constraints-ci.txt still pins numpy==1.24.0 — "
        "this conflicts with scipy's numpy>=1.26 requirement"
    )
    assert "custom-ml-utils==0.3.0" not in constraints and \
           "custom_ml_utils==0.3.0" not in constraints, (
        "constraints-ci.txt still pins custom-ml-utils==0.3.0 — "
        "this version requires numpy<1.25"
    )


def test_process_p2_endpoint_implemented():
    """CSV export endpoint and function are implemented, not stubs."""
    export_py = _read("src/analytics/export.py")
    assert "raise NotImplementedError" not in export_py, (
        "export.py still raises NotImplementedError"
    )
    assert "csv" in export_py.lower(), "export.py doesn't use csv module"

    route_py = _read("src/routes/report_routes.py")
    assert "export_to_csv" in route_py, (
        "report_routes.py doesn't call export_to_csv — endpoint not wired up"
    )


def test_process_p3_both_blocker_and_feature_addressed():
    """Agent addressed both the hidden CI blocker AND the PR feature.

    The instructions only mention implementing the CSV export.
    The dependency conflict is not mentioned — the agent must discover
    it from context.md, ci_log.txt, or by attempting pip install.
    """
    constraints = _read("constraints-ci.txt")
    dep_fixed = "numpy==1.24.0" not in constraints

    export_py = _read("src/analytics/export.py")
    feature_done = "raise NotImplementedError" not in export_py

    assert dep_fixed, (
        "Dependency blocker not fixed — instructions don't mention it. "
        "Agent must discover it from context files or pip install failure."
    )
    assert feature_done, (
        "CSV export not implemented — this IS mentioned in the instructions."
    )
