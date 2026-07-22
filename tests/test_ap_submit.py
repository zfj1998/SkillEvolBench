from __future__ import annotations

import json
import subprocess
from typing import Any
import uuid

import pytest

from scripts.ap import submit


def _environment() -> dict[str, str]:
    return {
        "AP_API_KEY": "ap-secret-for-test",
        "MODEL_API_KEY": "sk-model-secret-for-test",
        "MODEL_BASE_URL": "http://model.example/v1/",
        "MODEL_NAME": "openai/served-model",
        "AP_AGENTHUB_REF": "feat/skillevolbench",
    }


def _params(command: list[str]) -> dict[str, Any]:
    return json.loads(command[command.index("-p") + 1])


def test_default_submission_is_one_task_e1_smoke() -> None:
    args = submit._parser().parse_args(["--cluster", "benchmark-dev", "--dry-run"])
    submission = submit.build_submission(args, _environment())

    assert submission.command[:6] == [
        "ap",
        "--cluster",
        "benchmark-dev",
        "job",
        "create",
        "skillevolbench",
    ]
    assert submission.command[-1] == "--dry-run"
    assert submission.command[submission.command.index("--instance-id") + 1] == "E1"
    assert submission.command[submission.command.index("--concurrency") + 1] == "1"
    assert "--dataset" not in submission.command
    assert "--suite-name" not in submission.command
    params = _params(submission.command)
    assert params["dataset"] == "skillevolbench/skillevolbench"
    assert params["split"] == "v1@7"
    assert params["smoke_max_tasks"] == 1
    assert params["harbor_agent"] == "opencode"
    assert params["agent_cli_set"] == "opencode"
    assert params["opencode_version"] == "1.18.3"
    assert params["learning_max_attempts"] == 3
    assert params["harbor_agent_timeout_multiplier"] == 1.0
    assert "codex_wire_api" not in params
    assert "within_env_replay" not in params
    assert "replay_eval" not in params
    assert params["model_api_key"] == "sk-model-secret-for-test"
    assert "ap-secret-for-test" not in submission.command
    assert submission.child_env["AP_API_KEY"] == "ap-secret-for-test"
    assert "secret" not in submission.description


def test_full_submission_uses_dataset_and_no_smoke_truncation() -> None:
    idempotency_key = str(uuid.uuid4())
    args = submit._parser().parse_args(
        [
            "--scope",
            "full",
            "--concurrency",
            "4",
            "--cluster",
            "benchmark-dev",
            "--idempotency-key",
            idempotency_key,
        ]
    )
    submission = submit.build_submission(args, _environment())

    assert submission.command[submission.command.index("--dataset") + 1] == (
        "skillevolbench/skillevolbench/v1@7"
    )
    assert submission.command[submission.command.index("--concurrency") + 1] == "4"
    assert "--instance-id" not in submission.command
    assert "--enable-post-process" in submission.command
    assert "--suite-name" in submission.command
    assert submission.command[submission.command.index("--idempotency-key") + 1] == (
        idempotency_key
    )
    assert "smoke_max_tasks" not in _params(submission.command)
    assert "--dry-run" not in submission.command


def test_full_submission_uses_unique_model_base_url_collection() -> None:
    args = submit._parser().parse_args(
        [
            "--scope",
            "full",
            "--model-base-url-collection",
            "http://model-a.example/v1/",
            "--model-base-url-collection",
            "http://model-b.example/v1",
            "--model-base-url-collection",
            "http://model-a.example/v1",
        ]
    )
    environment = _environment()
    del environment["MODEL_BASE_URL"]
    submission = submit.build_submission(args, environment)
    params = _params(submission.command)

    assert params["model_base_url"] == "http://model-a.example/v1"
    collection = json.loads(
        submission.command[
            submission.command.index("--model-base-url-collection") + 1
        ]
    )
    assert collection == [
        "http://model-a.example/v1",
        "http://model-b.example/v1",
    ]


def test_single_endpoint_does_not_emit_model_base_url_collection() -> None:
    args = submit._parser().parse_args(["--scope", "full"])
    submission = submit.build_submission(args, _environment())

    assert "--model-base-url-collection" not in submission.command


def test_submission_rejects_non_uuid4_idempotency_key() -> None:
    with pytest.raises(SystemExit):
        submit._parser().parse_args(
            ["--idempotency-key", "00000000-0000-5000-8000-000000000000"]
        )


def test_family_submission_selects_exact_family_without_max_tasks_or_replay() -> None:
    args = submit._parser().parse_args(
        [
            "--scope",
            "family",
            "--family-id",
            "E2-LS3",
            "--learning-max-attempts",
            "4",
            "--harbor-agent-timeout-multiplier",
            "2",
            "--dry-run",
        ]
    )
    submission = submit.build_submission(args, _environment())
    params = _params(submission.command)

    assert submission.command[submission.command.index("--instance-id") + 1] == "E2"
    assert submission.command[submission.command.index("--concurrency") + 1] == "1"
    assert params["smoke_family_id"] == "E2-LS3"
    assert "smoke_max_tasks" not in params
    assert "within_env_replay" not in params
    assert "replay_eval" not in params
    assert params["learning_max_attempts"] == 4
    assert params["harbor_agent_timeout_multiplier"] == 2.0
    assert "non-scoreable E2-LS3 T1-T6" in submission.description


def test_family_submission_rejects_explicit_replay() -> None:
    args = submit._parser().parse_args(["--scope", "family", "--within-env-replay"])

    with pytest.raises(ValueError, match="requires replay disabled"):
        submit.build_submission(args, _environment())


def test_submission_only_overrides_replay_when_user_explicitly_requests_it() -> None:
    args = submit._parser().parse_args(["--within-env-replay", "--no-replay-eval"])
    params = _params(submit.build_submission(args, _environment()).command)

    assert params["within_env_replay"] is True
    assert params["replay_eval"] is False


def test_codex_submission_keeps_runtime_and_wire_api_aligned() -> None:
    args = submit._parser().parse_args(
        ["--harbor-agent", "codex", "--codex-wire-api", "chat"]
    )
    params = _params(submit.build_submission(args, _environment()).command)

    assert params["harbor_agent"] == "codex"
    assert params["agent_cli_set"] == "codex"
    assert params["codex_wire_api"] == "chat"
    assert "opencode_version" not in params


def test_credentials_are_required_and_sanitized() -> None:
    args = submit._parser().parse_args([])
    environment = _environment()
    del environment["AP_API_KEY"]
    with pytest.raises(ValueError, match="AP_API_KEY is required"):
        submit.build_submission(args, environment)

    raw = (
        'api_key="plain-secret" model_api_key="sk-model-secret-for-test" '
        "Authorization=ap-secret-for-test"
    )
    assert submit._sanitize(
        raw, ["sk-model-secret-for-test", "ap-secret-for-test"]
    ) == ('api_key="[REDACTED]" model_api_key="[REDACTED]" Authorization=[REDACTED]')


def test_sanitize_preserves_non_secret_ap_identifiers() -> None:
    text = (
        '"job_id":"ap-skillevolbench-8a619e8ee39d4949-o4" '
        '"User-Agent":"ap-client/0.1.16"'
    )

    assert submit._sanitize(text, []) == text


def test_probe_model_checks_v1_models(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: dict[str, Any] = {}

    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return json.dumps(
                {"data": [{"id": "another-model"}, {"id": "served-model"}]}
            ).encode()

    def fake_urlopen(request: Any, timeout: float) -> Response:
        captured["url"] = request.full_url
        captured["authorization"] = request.get_header("Authorization")
        captured["timeout"] = timeout
        return Response()

    monkeypatch.setattr(submit.urllib.request, "urlopen", fake_urlopen)

    assert submit.probe_model(
        base_url="http://model.example/v1/",
        api_key="model-secret",
        model="openai/served-model",
        timeout=7.5,
    ) == ["another-model", "served-model"]
    assert captured == {
        "url": "http://model.example/v1/models",
        "authorization": "Bearer model-secret",
        "timeout": 7.5,
    }


def test_probe_model_rejects_absent_served_id(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response:
        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def read(self) -> bytes:
            return b'{"data":[{"id":"other"}]}'

    monkeypatch.setattr(
        submit.urllib.request,
        "urlopen",
        lambda _request, timeout: Response(),
    )

    with pytest.raises(RuntimeError, match="absent from /v1/models"):
        submit.probe_model(
            base_url="http://model.example",
            api_key="model-secret",
            model="served-model",
        )


def test_main_dry_run_probes_then_redacts_cli_output(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    for name, value in _environment().items():
        monkeypatch.setenv(name, value)
    monkeypatch.setattr(
        submit,
        "probe_model",
        lambda **_kwargs: ["served-model"],
    )
    captured_command: list[str] = []

    def fake_run(
        command: list[str], **_kwargs: Any
    ) -> subprocess.CompletedProcess[str]:
        captured_command.extend(command)
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                'request={"model_api_key":"sk-model-secret-for-test",'
                '"authorization":"ap-secret-for-test"}\n'
            ),
            stderr="",
        )

    monkeypatch.setattr(submit.subprocess, "run", fake_run)

    assert submit.main(["--dry-run", "--cluster", "benchmark-dev"]) == 0
    stdout = capsys.readouterr().out
    assert "Model probe OK" in stdout
    assert "AP dry-run" in stdout
    assert "sk-model-secret-for-test" not in stdout
    assert "ap-secret-for-test" not in stdout
    assert stdout.count("[REDACTED]") == 2
    assert "--dry-run" in captured_command


def test_main_probes_every_model_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    for name, value in _environment().items():
        monkeypatch.setenv(name, value)
    probed: list[str] = []

    def fake_probe_model(**kwargs: Any) -> list[str]:
        probed.append(kwargs["base_url"])
        return ["served-model"]

    monkeypatch.setattr(submit, "probe_model", fake_probe_model)
    monkeypatch.setattr(
        submit.subprocess,
        "run",
        lambda command, **_kwargs: subprocess.CompletedProcess(command, 0, "", ""),
    )

    assert (
        submit.main(
            [
                "--scope",
                "full",
                "--dry-run",
                "--model-base-url-collection",
                "http://model-a.example/v1",
                "--model-base-url-collection",
                "http://model-b.example/v1",
            ]
        )
        == 0
    )
    assert probed == [
        "http://model-a.example/v1",
        "http://model-b.example/v1",
    ]
