from __future__ import annotations

import argparse
import importlib.util
import json
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
        elif script == "build_t56_oracle_report.py":
            (watcher.analysis_dir / "t56_report_data.json").write_text(
                json.dumps({"coverage": [{} for _ in range(48)]}) + "\n",
                encoding="utf-8",
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.md").write_text(
                "# report\n", encoding="utf-8"
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.html").write_text(
                "<!doctype html><html><script>const ok = true;</script></html>\n",
                encoding="utf-8",
            )
        for name in (
            "t56_tasks.csv",
            "t56_verifier_audit.csv",
        ):
            (watcher.analysis_dir / name).write_text("header\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(watcher, "run_command", fake_run)
    watcher.refresh_analysis({})

    by_script = {Path(command[1]).name: command for command in commands}
    collector = by_script["build_t56_oracle_study.py"]
    report = by_script["build_t56_oracle_report.py"]
    assert "--reference-audit" not in collector
    index = report.index("--reference-audit")
    assert report[index + 1] == str(reference)


def test_analysis_signature_ignores_ap_updated_at(
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
    calls = 0

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        script = Path(command[1]).name
        if script == "build_t56_oracle_study.py":
            (watcher.analysis_dir / "t56_evidence.json").write_text("{}\n")
        elif script == "audit_t56_verifiers.py":
            (watcher.analysis_dir / "t56_verifier_audit.json").write_text("{}\n")
        elif script == "build_t56_oracle_report.py":
            (watcher.analysis_dir / "t56_report_data.json").write_text(
                json.dumps({"coverage": [{} for _ in range(48)]}) + "\n"
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.md").write_text(
                "# report\n"
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.html").write_text(
                "<!doctype html><html><script>let ok = true;</script></html>\n"
            )
        for name in ("t56_tasks.csv", "t56_verifier_audit.csv"):
            (watcher.analysis_dir / name).write_text("header\n")
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(watcher, "run_command", fake_run)
    first = {"job-1": {"status": "Running", "updated_at": "first"}}
    second = {"job-1": {"status": "Running", "updated_at": "second"}}
    watcher.refresh_analysis(first)
    first_call_count = calls
    watcher.refresh_analysis(second)
    assert first_call_count > 0
    assert calls == first_call_count


def test_invalid_report_does_not_advance_analysis_marker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        state_dir=tmp_path / "watcher",
        evidence_dir=tmp_path / "raw",
        cluster="test-cluster",
        repo_root=ROOT,
        poll_sec=60,
        analysis_timeout_sec=60,
    )
    watcher = WATCH.Watcher(args)

    def fake_run(command: list[str], **_: object) -> subprocess.CompletedProcess[str]:
        script = Path(command[1]).name
        if script == "build_t56_oracle_study.py":
            (watcher.analysis_dir / "t56_evidence.json").write_text("{}\n")
            (watcher.analysis_dir / "t56_tasks.csv").write_text("header\n")
        elif script == "audit_t56_verifiers.py":
            (watcher.analysis_dir / "t56_verifier_audit.json").write_text("{}\n")
            (watcher.analysis_dir / "t56_verifier_audit.csv").write_text("header\n")
        elif script == "build_t56_oracle_report.py":
            (watcher.analysis_dir / "t56_report_data.json").write_text(
                json.dumps({"coverage": []}) + "\n"
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.md").write_text(
                "# report\n"
            )
            (watcher.analysis_dir / "t56_oracle_study_report_zh.html").write_text(
                "<!doctype html><html><script>let ok = true;</script></html>\n"
            )
        return subprocess.CompletedProcess(command, 0, "{}", "")

    monkeypatch.setattr(watcher, "run_command", fake_run)
    watcher.refresh_analysis({})
    assert not (watcher.state_dir / "analysis.json").exists()
    assert "analysis_validation_failed" in (watcher.state_dir / "events.jsonl").read_text()


def test_quarantine_is_released_only_after_new_scanner_passes(
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.setenv("AP_API_KEY", "test-only-key")
    args = argparse.Namespace(
        state_dir=tmp_path / "watcher",
        evidence_dir=tmp_path / "raw",
        cluster="test-cluster",
        repo_root=ROOT,
        poll_sec=60,
        scan_timeout_sec=60,
    )
    watcher = WATCH.Watcher(args)
    job = {"job_id": "job-1", "label": "exact-E5", "status": "Succeeded"}
    quarantine = watcher.evidence_dir / ".quarantine" / "exact-E5" / "job-1"
    quarantine.mkdir(parents=True)
    (quarantine / "result.json").write_text("{}\n", encoding="utf-8")
    write_marker = {
        "completed": False,
        "unsafe": True,
        "job_id": "job-1",
        "quarantine": str(quarantine),
        "scanner_sha256": "old-policy",
        "scan_summary": {"clean": False},
    }
    WATCH.write_json(watcher.export_marker("job-1"), write_marker)
    monkeypatch.setattr(
        watcher,
        "run_command",
        lambda command, **kwargs: subprocess.CompletedProcess(
            command, 0, '{"clean": true}', ""
        ),
    )

    watcher.recheck_quarantined_export(job)

    marker = WATCH.read_json(watcher.export_marker("job-1"), {})
    assert marker["completed"] is True
    assert marker["released_from_quarantine"] is True
    assert marker["previous_scan_summary"] == {"clean": False}
    assert not quarantine.exists()
    assert Path(marker["destination"], "result.json").is_file()
