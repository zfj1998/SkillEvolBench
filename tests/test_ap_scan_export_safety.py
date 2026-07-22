from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from scripts.ap import scan_export_safety as scanner


def test_clean_tree_is_read_only_and_artifacts_transport_is_skipped(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    regular = root / "metrics.json"
    regular.write_text('{"task_score": 1.0}\n', encoding="utf-8")
    transport = root / "artifacts.json"
    transport.write_text(
        '{"url":"https://transport.invalid/a?X-Amz-Signature=must-skip"}\n',
        encoding="utf-8",
    )
    before = {path: path.read_bytes() for path in (regular, transport)}

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is True
    assert report["scan_complete"] is True
    assert report["finding_count"] == 0
    assert report["scan_counts"]["regular_files"] == 2  # type: ignore[index]
    assert report["scan_counts"]["skipped_artifacts_json"] == 1  # type: ignore[index]
    assert {path: path.read_bytes() for path in (regular, transport)} == before
    assert report["policy"]["writes_performed"] is False  # type: ignore[index]


def test_content_categories_and_exact_environment_value_are_aggregated(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    exact = "env-secret-9x8y7z6w"
    payload = root / "trajectory.log"
    payload.write_text(
        "\n".join(
            (
                "-----BEGIN " + "OPENSSH PRIVATE KEY-----",
                "https://store.invalid/a?X-Amz-Signature=signed-value",
                "runtime=sevb-no-auth-0123456789abcdef",
                'client_secret = "sk-liveCredential_24680abcd"',
                f"opaque={exact}",
            )
        ),
        encoding="utf-8",
    )

    report = scanner.scan_tree(
        root,
        environment={"OPENAI_API_KEY": exact},
    )

    assert report["clean"] is False
    counts = report["category_counts"]
    assert counts["private_key_header"] == 1  # type: ignore[index]
    assert counts["signed_url_query"] == 1  # type: ignore[index]
    assert counts["no_auth_sentinel"] == 1  # type: ignore[index]
    assert counts["credential_assignment"] == 1  # type: ignore[index]
    assert counts["exact_secret_value"] == 1  # type: ignore[index]
    assert report["finding_count"] == 5
    assert report["scan_counts"]["exact_secret_values_loaded"] == 1  # type: ignore[index]


def test_filename_and_symlink_target_are_scanned_without_following(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    (root / "sevb-no-auth-filename-value").write_text("safe body", encoding="utf-8")
    link = root / "transport-link"
    link.symlink_to("../outside?Signature=target-secret")

    report = scanner.scan_tree(root, environment={})

    counts = report["category_counts"]
    assert counts["no_auth_sentinel"] == 1  # type: ignore[index]
    assert counts["signed_url_query"] == 1  # type: ignore[index]
    assert counts["symlink_escapes_root"] == 1  # type: ignore[index]
    surfaces = report["surface_counts"]
    assert surfaces["filename"] == 1  # type: ignore[index]
    assert surfaces["symlink_target"] == 1  # type: ignore[index]
    assert surfaces["symlink_safety"] == 1  # type: ignore[index]
    assert link.is_symlink()


def test_standard_dot_venv_python_link_is_preserved_and_clean(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    link = root / "runs" / "trial" / "artifacts" / "root" / "task"
    link = link / "project" / ".venv" / "bin" / "python"
    link.parent.mkdir(parents=True)
    link.symlink_to("/usr/bin/python3.12")

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is True
    assert report["category_counts"]["symlink_escapes_root"] == 0  # type: ignore[index]
    assert report["scan_counts"]["symlinks"] == 1  # type: ignore[index]
    assert link.is_symlink()


@pytest.mark.parametrize(
    ("relative", "target"),
    [
        ("runs/trial/artifacts/root/task/project/venv/bin/python", "/usr/bin/python3.12"),
        ("runs/trial/artifacts/root/task/project/.venv/bin/pip", "/usr/bin/python3.12"),
        ("runs/trial/artifacts/root/task/project/.venv/bin/python", "/bin/sh"),
    ],
)
def test_lookalike_external_venv_link_remains_unsafe(
    tmp_path: Path,
    relative: str,
    target: str,
) -> None:
    root = tmp_path / "export"
    link = root / relative
    link.parent.mkdir(parents=True)
    link.symlink_to(target)

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is False
    assert report["category_counts"]["symlink_escapes_root"] == 1  # type: ignore[index]


def test_generic_assignment_ignores_placeholders_and_references(tmp_path: Path) -> None:
    root = tmp_path / "export"
    root.mkdir()
    (root / "config.txt").write_text(
        "\n".join(
            (
                'api_key = "[REDACTED]"',
                'password = "${PASSWORD_FROM_ENV}"',
                'client_secret = "settings.client_secret"',
                'access_token = "example-token-value"',
                'registry_password = "xxxxxxxxxxxxxxxx"',
                'OPENAI_API_KEY = "{env:OPENAI_API_KEY}"',
                'model_api_key = "sk-example-not-a-live-key"',
                'api_key = "legacy_key_24680"',
            )
        ),
        encoding="utf-8",
    )

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is True
    assert report["category_counts"]["credential_assignment"] == 0  # type: ignore[index]


@pytest.mark.parametrize(
    ("token", "payload"),
    (
        (
            "token-e2-ls4-t1",
            'access_token = "token-e2-ls4-t1"',
        ),
        (
            "token-e2-ls4-t1",
            'authorization = "Bearer token-e2-ls4-t1\\\\"',
        ),
        (
            "token-e2-ls4-t6",
            'authorization = "Bearer token-e2-ls4-t6\\\\\\""',
        ),
        (
            "token-e2-ls4-t1",
            "authorization: Bearer token-e2-ls4-t1`.",
        ),
    ),
)
def test_exact_committed_mock_bearer_tokens_are_clean_through_serialization(
    tmp_path: Path,
    token: str,
    payload: str,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    (root / "event.bin").write_bytes(payload.encode())

    report = scanner.scan_tree(root, environment={})

    assert token.encode() in scanner.SKILLEVOLBENCH_MOCK_BEARER_TOKENS
    assert report["clean"] is True
    assert report["category_counts"]["credential_assignment"] == 0  # type: ignore[index]


def test_mock_bearer_allowlist_matches_committed_e2_fixtures() -> None:
    repository = Path(__file__).resolve().parents[1]
    fixtures = {
        "benchmark/tasks/auth-list-detail-save-4-step/environment/mock_api.py": (
            "token-e2-ls4-t1"
        ),
        "benchmark/tasks/full-orchestration-retry-validate/environment/mock_api.py": (
            "token-e2-ls4-t6"
        ),
    }

    for relative_path, token in fixtures.items():
        source = (repository / relative_path).read_text(encoding="utf-8")
        assert f"TOKEN = '{token}'" in source
    assert scanner.SKILLEVOLBENCH_MOCK_BEARER_TOKENS == frozenset(
        token.encode() for token in fixtures.values()
    )


@pytest.mark.parametrize(
    "value",
    (
        "Bearer token-e2-ls4-t1-suffix",
        "Bearer token-e2-ls4-t6x",
        "Bearer unrelated-production-shaped-token-123456",
    ),
)
def test_mock_bearer_near_misses_and_unrelated_values_remain_findings(
    tmp_path: Path,
    value: str,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    (root / "event.json").write_text(
        f'authorization = "{value}\\\\"',
        encoding="utf-8",
    )

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is False
    assert report["category_counts"]["credential_assignment"] == 1  # type: ignore[index]


def test_exact_environment_secret_wins_over_mock_fixture_exception(
    tmp_path: Path,
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    fixture = "token-e2-ls4-t1"
    (root / "event.json").write_text(
        f'authorization = "Bearer {fixture}\\\\"',
        encoding="utf-8",
    )

    report = scanner.scan_tree(root, environment={"OPENAI_API_KEY": fixture})

    assert report["clean"] is False
    assert report["category_counts"]["credential_assignment"] == 0  # type: ignore[index]
    assert report["category_counts"]["exact_secret_value"] == 1  # type: ignore[index]


def test_prefixed_key_and_chunk_boundary_are_detected(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    monkeypatch.setattr(scanner, "CHUNK_SIZE", 17)
    (root / "binary.bin").write_bytes(
        b"0123456789abcdef" + b'OPENAI_API_KEY="sk-liveKey_123456789abcd"'
    )

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is False
    assert report["category_counts"]["credential_assignment"] == 1  # type: ignore[index]


def test_only_named_nontrivial_environment_values_are_loaded(tmp_path: Path) -> None:
    root = tmp_path / "export"
    root.mkdir()
    (root / "trace.txt").write_text(
        "unrelated-long-secret plus named-secret-1234", encoding="utf-8"
    )

    report = scanner.scan_tree(
        root,
        environment={
            "UNRELATED_SECRET": "unrelated-long-secret",
            "OPENAI_API_KEY": "named-secret-1234",
            "AP_API_KEY": "NONE",
        },
    )

    assert report["clean"] is False
    assert report["category_counts"]["exact_secret_value"] == 1  # type: ignore[index]
    assert report["scan_counts"]["exact_secret_values_loaded"] == 1  # type: ignore[index]
    assert report["scan_counts"]["exact_secret_values_ignored"] == 1  # type: ignore[index]


def test_unreadable_file_is_fail_closed_without_leaking_path(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    blocked = root / "name-containing-private-value"
    blocked.write_text("body-containing-private-value", encoding="utf-8")
    original_open = scanner.os.open

    def guarded_open(path: os.PathLike[str] | str, flags: int, *args: object) -> int:
        if Path(path) == blocked:
            raise PermissionError("must not be rendered")
        return original_open(path, flags, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(scanner.os, "open", guarded_open)

    report = scanner.scan_tree(root, environment={})
    rendered = json.dumps(report)

    assert report["clean"] is False
    assert report["scan_complete"] is False
    assert report["category_counts"]["unreadable_file"] == 1  # type: ignore[index]
    assert "name-containing-private-value" not in rendered
    assert "body-containing-private-value" not in rendered
    assert "must not be rendered" not in rendered


def test_skipped_artifacts_transport_must_still_be_readable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    transport = root / "artifacts.json"
    transport.write_text("signed transport content is excluded", encoding="utf-8")
    original_open = scanner.os.open

    def guarded_open(path: os.PathLike[str] | str, flags: int, *args: object) -> int:
        if Path(path) == transport:
            raise PermissionError("not rendered")
        return original_open(path, flags, *args)  # type: ignore[arg-type]

    monkeypatch.setattr(scanner.os, "open", guarded_open)

    report = scanner.scan_tree(root, environment={})

    assert report["clean"] is False
    assert report["scan_complete"] is False
    assert report["scan_counts"]["skipped_artifacts_json"] == 1  # type: ignore[index]
    assert report["category_counts"]["unreadable_file"] == 1  # type: ignore[index]


def test_cli_json_never_prints_matched_values_or_paths(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    root = tmp_path / "export"
    root.mkdir()
    secret = "cli-secret-A1B2C3D4"
    secret_path = root / f"leaky-{secret}"
    secret_path.write_text(f'api_key="{secret}"\n', encoding="utf-8")
    monkeypatch.setenv("OPENAI_API_KEY", secret)

    assert scanner.main([str(root)]) == 1

    captured = capsys.readouterr()
    report = json.loads(captured.out)
    assert report["clean"] is False
    assert secret not in captured.out
    assert secret not in captured.err
    assert str(secret_path) not in captured.out
    assert report["policy"]["paths_reported"] is False


def test_root_symlink_is_not_followed(tmp_path: Path) -> None:
    real = tmp_path / "real"
    real.mkdir()
    (real / "secret.txt").write_text(
        "-----BEGIN " + "PRIVATE KEY-----", encoding="utf-8"
    )
    link = tmp_path / "export-link"
    link.symlink_to(real, target_is_directory=True)

    report = scanner.scan_tree(link, environment={})

    assert report["clean"] is False
    assert report["scan_complete"] is False
    assert report["category_counts"]["root_is_symlink"] == 1  # type: ignore[index]
    assert report["category_counts"]["private_key_header"] == 0  # type: ignore[index]
