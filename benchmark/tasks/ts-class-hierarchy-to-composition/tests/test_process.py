from __future__ import annotations

import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks


def _extends_removed():
    data_text = read_text(PROJECT / "src" / "DataProcessor.ts")
    specialized_text = read_text(PROJECT / "src" / "SpecializedProcessor.ts")
    assert "extends BaseProcessor" not in data_text, "DataProcessor still extends BaseProcessor"
    assert "extends DataProcessor" not in specialized_text, "SpecializedProcessor still extends DataProcessor"
    return "extends chain removed"


def _constructor_injection_present():
    text = read_text(PROJECT / "src" / "DataProcessor.ts") + read_text(PROJECT / "src" / "SpecializedProcessor.ts")
    assert "constructor(" in text and ("validator" in text or "transformer" in text or "enricher" in text), "constructor injection not found"
    return "constructor injection present"


def _no_any():
    text = read_text(PROJECT / "src" / "BaseProcessor.ts") + read_text(PROJECT / "src" / "DataProcessor.ts") + read_text(PROJECT / "src" / "SpecializedProcessor.ts")
    assert ": any" not in text and "<any>" not in text, "type weakening with any detected"
    return "no any detected"


def run():
    public = run_checks("public", [("extends_removed", _extends_removed)])
    hidden = run_checks(
        "hidden",
        [
            ("constructor_injection_present", _constructor_injection_present),
            ("no_any", _no_any),
        ],
    )
    return emit_report("E1-LS3-T3", public, hidden)


if __name__ == "__main__":
    print_report(run())
