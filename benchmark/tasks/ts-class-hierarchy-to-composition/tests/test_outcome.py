from __future__ import annotations

import shutil
import sys
from pathlib import Path

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SKILLSBENCH_ROOT = Path(__file__).resolve().parents[4]
if str(SKILLSBENCH_ROOT) not in sys.path:
    sys.path.insert(0, str(SKILLSBENCH_ROOT))

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks, run_subprocess


def _source_files_exist():
    required = [
        PROJECT / "src" / "BaseProcessor.ts",
        PROJECT / "src" / "DataProcessor.ts",
        PROJECT / "src" / "SpecializedProcessor.ts",
        PROJECT / "src" / "types.ts",
    ]
    missing = [str(path) for path in required if not path.exists()]
    assert not missing, f"missing files: {missing}"
    return "all ts source files present"


def _strict_compile_if_available():
    tsc = shutil.which("tsc")
    if not tsc:
        return "tsc unavailable in environment; compile check deferred"
    result = run_subprocess([tsc, "--noEmit"], PROJECT)
    assert result.returncode == 0, result.stdout + result.stderr
    return "tsc --noEmit passed"


def _composition_signals_present():
    text = read_text(PROJECT / "src" / "SpecializedProcessor.ts") + read_text(PROJECT / "src" / "DataProcessor.ts")
    assert "validator" in text or "transformer" in text or "enricher" in text, "injectable components not found"
    return "composition-oriented names found"


def _runtime_processor_behavior_if_available():
    npm = shutil.which("npm")
    node = shutil.which("node")
    if not npm or not node:
        return "npm/node unavailable in environment; runtime behavior check deferred"
    install = run_subprocess([npm, "install", "--no-audit", "--no-fund"], PROJECT)
    assert install.returncode == 0, install.stdout + install.stderr
    build = run_subprocess([npm, "run", "build"], PROJECT)
    assert build.returncode == 0, build.stdout + build.stderr
    compiled_test = PROJECT / "dist" / "public_tests" / "processor.test.js"
    assert compiled_test.exists(), "compiled processor behavior test missing"
    result = run_subprocess([node, str(compiled_test)], PROJECT)
    assert result.returncode == 0, result.stdout + result.stderr
    return "compiled processor behavior test passed"


def run():
    public = run_checks(
        "public",
        [
            ("source_files_exist", _source_files_exist),
            ("strict_compile_if_available", _strict_compile_if_available),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("composition_signals_present", _composition_signals_present),
            ("runtime_processor_behavior_if_available", _runtime_processor_behavior_if_available),
        ],
    )
    return emit_report("E1-LS3-T3", public, hidden, notes=["This verifier uses compile checks when TypeScript is available."])


if __name__ == "__main__":
    print_report(run())
