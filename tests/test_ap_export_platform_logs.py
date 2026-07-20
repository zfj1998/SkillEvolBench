from __future__ import annotations

import json
import stat
from collections import defaultdict
from pathlib import Path
from typing import Any

import pytest

from scripts.ap import export_platform_logs as exporter


JOB_ID = "ap-skillevolbench-test-o4"
CLUSTER = "benchmark-dev"


class FakeClient:
    def __init__(
        self,
        logs: dict[str, list[Any]],
        *,
        status: str = "Succeeded",
        second_logs: dict[str, list[Any]] | None = None,
        second_status: str | None = None,
        second_containers: list[str] | None = None,
    ) -> None:
        self.logs = logs
        self.second_logs = second_logs or logs
        self.status = status
        self.second_status = second_status or status
        self.second_containers = second_containers
        self.job_calls = 0
        self.container_calls = 0
        self.log_calls: list[tuple[str, int, int]] = []
        self.log_passes: defaultdict[str, int] = defaultdict(int)

    def get_job(self, job_id: str, **_kwargs: Any) -> dict[str, Any]:
        assert job_id == JOB_ID
        self.job_calls += 1
        return {
            "job_id": JOB_ID,
            "ap_cluster_name": CLUSTER,
            "status": self.status if self.job_calls == 1 else self.second_status,
            "attempt": 0,
            "finished_at": "2026-07-21T00:00:00",
            "pod_uid": "pod-test",
        }

    def get_job_containers(self, job_id: str) -> dict[str, Any]:
        assert job_id == JOB_ID
        self.container_calls += 1
        containers = list(self.logs)
        if self.container_calls > 1 and self.second_containers is not None:
            containers = self.second_containers
        return {"job_id": JOB_ID, "containers": containers}

    def get_job_logs(
        self,
        job_id: str,
        container: str | None = None,
        offset: int | None = 0,
        limit: int | None = exporter.PAGE_LIMIT,
    ) -> dict[str, Any]:
        assert job_id == JOB_ID
        assert container is not None
        assert offset is not None
        assert limit == 500
        self.log_calls.append((container, offset, limit))
        if offset == 0:
            self.log_passes[container] += 1
        values = (
            self.logs[container]
            if self.log_passes[container] == 1
            else self.second_logs[container]
        )
        page = values[offset : offset + limit]
        next_offset = offset + len(page) if offset + len(page) < len(values) else None
        return {
            "offset": offset,
            "logs": page,
            "next_offset": next_offset,
        }


def _export_dir(tmp_path: Path) -> Path:
    export_dir = tmp_path / "export"
    export_dir.mkdir()
    (export_dir / "job.json").write_text(
        json.dumps(
            {
                "job_id": JOB_ID,
                "ap_cluster_name": CLUSTER,
                "status": "Succeeded",
            }
        ),
        encoding="utf-8",
    )
    return export_dir


def test_export_pages_every_container_and_verifies_second_pass(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    export_dir = _export_dir(tmp_path)
    (export_dir / "artifacts.json").write_text(
        "not-json and must not be opened: https://signed.example/secret",
        encoding="utf-8",
    )
    original_read_text = Path.read_text

    def guarded_read_text(path: Path, *args: Any, **kwargs: Any) -> str:
        if path.name == "artifacts.json":
            raise AssertionError("artifacts.json must never be read")
        return original_read_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    main_logs = [
        {"timestamp": f"t{i}", "content": f"line-{i}"} for i in range(501)
    ]
    daemon_logs = ["ready", "done"]
    client = FakeClient({"main": main_logs, "docker-daemon": daemon_logs})

    manifest = exporter.export_job_logs(
        client,
        job_id=JOB_ID,
        export_dir=export_dir,
        cluster=CLUSTER,
    )

    assert client.job_calls == 2
    assert client.container_calls == 2
    assert client.log_calls == [
        ("docker-daemon", 0, 500),
        ("main", 0, 500),
        ("main", 500, 500),
        ("docker-daemon", 0, 500),
        ("main", 0, 500),
        ("main", 500, 500),
    ]
    assert manifest["terminal_job_verified_by_two_api_reads"] is True
    assert manifest["logs_verified_by_second_api_pass"] is True
    assert manifest["local_hash_and_size_verified"] is True
    assert manifest["page_limit"] == 500
    assert manifest["container_count"] == 2
    assert manifest["containers"]["main"]["entry_count"] == 501
    assert manifest["containers"]["main"]["pages"] == [
        {"offset": 0, "count": 500, "next_offset": 500},
        {"offset": 500, "count": 1, "next_offset": None},
    ]

    logs_dir = export_dir / "logs"
    assert stat.S_IMODE(logs_dir.stat().st_mode) == 0o700
    for name in ("main.log", "docker-daemon.log", exporter.MANIFEST_NAME):
        assert stat.S_IMODE((logs_dir / name).stat().st_mode) == 0o600
    assert not list(logs_dir.glob("*.part"))
    written_manifest = json.loads(
        (logs_dir / exporter.MANIFEST_NAME).read_text(encoding="utf-8")
    )
    assert written_manifest == manifest


def test_nonterminal_job_is_rejected_before_logs_are_requested(tmp_path: Path) -> None:
    client = FakeClient({"main": ["line"]}, status="Running")

    with pytest.raises(exporter.ExportError, match="job is not terminal"):
        exporter.export_job_logs(
            client,
            job_id=JOB_ID,
            export_dir=_export_dir(tmp_path),
            cluster=CLUSTER,
        )

    assert client.job_calls == 1
    assert client.container_calls == 0
    assert client.log_calls == []


def test_symlinked_export_directory_is_rejected(tmp_path: Path) -> None:
    export_dir = _export_dir(tmp_path)
    symlink = tmp_path / "export-link"
    symlink.symlink_to(export_dir, target_is_directory=True)
    client = FakeClient({"main": ["line"]})

    with pytest.raises(exporter.ExportError, match="real AP export directory"):
        exporter.export_job_logs(
            client,
            job_id=JOB_ID,
            export_dir=symlink,
            cluster=CLUSTER,
        )

    assert client.job_calls == 0


def test_second_api_pass_mismatch_does_not_publish_manifest(tmp_path: Path) -> None:
    export_dir = _export_dir(tmp_path)
    logs_dir = export_dir / "logs"
    logs_dir.mkdir()
    (logs_dir / exporter.MANIFEST_NAME).write_text(
        '{"stale": true}\n', encoding="utf-8"
    )
    client = FakeClient(
        {"main": ["stable", "first"]},
        second_logs={"main": ["stable", "changed"]},
    )

    with pytest.raises(exporter.ExportError, match="second API pass mismatch"):
        exporter.export_job_logs(
            client,
            job_id=JOB_ID,
            export_dir=export_dir,
            cluster=CLUSTER,
        )

    assert (export_dir / "logs" / "main.log").is_file()
    assert not (export_dir / "logs" / exporter.MANIFEST_NAME).exists()


def test_changed_terminal_job_identity_is_rejected(tmp_path: Path) -> None:
    client = FakeClient(
        {"main": ["line"]},
        second_status="Failed",
    )

    with pytest.raises(exporter.ExportError, match="job identity changed"):
        exporter.export_job_logs(
            client,
            job_id=JOB_ID,
            export_dir=_export_dir(tmp_path),
            cluster=CLUSTER,
        )


def test_changed_container_set_is_rejected(tmp_path: Path) -> None:
    client = FakeClient(
        {"main": ["line"]},
        second_containers=["main", "late-sidecar"],
    )

    with pytest.raises(exporter.ExportError, match="container set changed"):
        exporter.export_job_logs(
            client,
            job_id=JOB_ID,
            export_dir=_export_dir(tmp_path),
            cluster=CLUSTER,
        )


def test_local_hash_mismatch_is_rejected(tmp_path: Path) -> None:
    destination = tmp_path / "main.log"
    client = FakeClient({"main": ["one", "two"]})
    expected = exporter.export_container(client, JOB_ID, "main", destination)
    destination.write_bytes(b"tampered\n")

    with pytest.raises(exporter.ExportError, match="local hash/size"):
        exporter.verify_container(
            client, JOB_ID, "main", destination, expected
        )


def test_failed_page_keeps_existing_destination_and_removes_part(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "main.log"
    destination.write_bytes(b"previous-complete-export\n")

    class FailingClient:
        def get_job_logs(self, **kwargs: Any) -> dict[str, Any]:
            if kwargs["offset"] == 0:
                return {
                    "offset": 0,
                    "logs": ["first"],
                    "next_offset": 1,
                }
            raise ConnectionError("simulated API failure")

    with pytest.raises(ConnectionError, match="simulated"):
        exporter.export_container(
            FailingClient(), JOB_ID, "main", destination
        )

    assert destination.read_bytes() == b"previous-complete-export\n"
    assert not list(tmp_path.glob("*.part"))


def test_invalid_page_offsets_are_rejected() -> None:
    class InvalidClient:
        def get_job_logs(self, **_kwargs: Any) -> dict[str, Any]:
            return {"offset": 0, "logs": ["one"], "next_offset": 2}

    with pytest.raises(exporter.ExportError, match="non-contiguous page"):
        list(exporter.pages(InvalidClient(), JOB_ID, "main"))


def test_colliding_sanitized_container_names_stay_unique() -> None:
    names = exporter._destination_names(["side/car", "side?car"])

    assert names["side/car"] != names["side?car"]
    assert all(name.startswith("side-car-") for name in names.values())
    assert all(name.endswith(".log") for name in names.values())


def test_cli_does_not_print_log_contents(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    secret_log_content = "credential-shaped-log-content"
    client = FakeClient({"main": [secret_log_content]})
    monkeypatch.setattr(exporter, "build_client", lambda _cluster: client)

    assert exporter.main(
        [JOB_ID, str(_export_dir(tmp_path)), "--cluster", CLUSTER]
    ) == 0

    captured = capsys.readouterr()
    assert secret_log_content not in captured.out
    assert secret_log_content not in captured.err
    assert "verified=true" in captured.out


def test_cli_suppresses_unexpected_exception_details(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    credential = "authorization-bearer-secret"

    def fail_client(_cluster: str) -> exporter.APLogClient:
        raise RuntimeError(credential)

    monkeypatch.setattr(exporter, "build_client", fail_client)

    with pytest.raises(SystemExit) as captured_exit:
        exporter.main(
            [JOB_ID, str(_export_dir(tmp_path)), "--cluster", CLUSTER]
        )

    captured = capsys.readouterr()
    assert captured_exit.value.code == 1
    assert credential not in captured.out
    assert credential not in captured.err
    assert "RuntimeError" in captured.err
