from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


def _module_split():
    python_files = [p for p in PROJECT.glob("*.py") if p.name not in {"__init__.py"}]
    assert len(python_files) >= 4, f"expected at least 4 focused modules, found {len(python_files)}"
    return {"python_files": [p.name for p in python_files]}


def _global_state_reduced():
    text = read_text(PROJECT / "processor.py")
    forbidden = ["ACTIVE_OUTPUT =", "ACTIVE_FORMAT =", "LAST_ERROR =", "TRANSFORM_COUNT =", "AUDIT_LOG ="]
    remaining = [name for name in forbidden if name in text]
    assert not remaining, f"global state still present: {remaining}"
    return "global state reduced"


def _plugin_registration_design():
    text = "\n".join(p.read_text(encoding="utf-8") for p in PROJECT.glob("*.py"))
    assert "register_plugin" in text or "load_plugins" in text or "PLUGIN_REGISTRY" in text, "plugin registration design missing"
    return "plugin registration design detected"


def run():
    public = run_checks("public", [("module_split", _module_split)])
    hidden = run_checks(
        "hidden",
        [
            ("global_state_reduced", _global_state_reduced),
            ("plugin_registration_design", _plugin_registration_design),
        ],
    )
    return emit_report("E1-LS3-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
