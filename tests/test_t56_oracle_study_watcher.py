from __future__ import annotations

import argparse
import importlib.util
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
SCRIPT = ROOT / "scripts/ap/watch_t56_oracle_study.py"
SPEC = importlib.util.spec_from_file_location("watch_t56_oracle_study", SCRIPT)
assert SPEC is not None and SPEC.loader is not None
WATCH = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(WATCH)


def test_reference_audit_is_routed_to_report_not_collector(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    state_dir = tmp_path / "watcher"
    evidence_dir = tmp_path / "raw"
    args = argparse.Namespace(
        state_dir=state_dir,
        evidence_dir=evidence_dir,
        cluster="test-cluster",
        repo_root=ROOT,
        poll_sec=60,
        analysis_timeout_sec=60,
    )
    watcher = WATCH.Watcher(args)
    watcher.analysis_dir.mkdir(parents=True)
    reference = watcher.analysis_dir / "reference_solution_audit_all_envs.json"
    reference.write_text("{}\n", encoding="utf-8")
    commands: list[list[str]] = []

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        commands.append(command)
        script = Path(command[1]).name
        if script == "build_t56_oracle_study.py":
            (watcher.analysis_dir / "t56_evidence.json").write_text(
                "{}\n", encoding="utf-8"
            )
        elif script == "audit_t56_verifiers.py":
            (watcher.analysis_dir / "t56_verifier_audit.json").write_text(
                "{}\n", encoding="utf-8"
            )
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(watcher, "run_command", fake_run)
    watcher.refresh_analysis({})

    by_script = {Path(command[1]).name: command for command in commands}
    collector = by_script["build_t56_oracle_study.py"]
    report = by_script["build_t56_oracle_report.py"]
    assert "--reference-audit" not in collector
    index = report.index("--reference-audit")
    assert report[index + 1] == str(reference)
