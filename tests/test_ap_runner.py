from __future__ import annotations

import json
import builtins
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ap import run_episode
from scripts.ap.mask_secrets import mask_tree
from skillevolbench.baselines import load_baseline
from skillevolbench.components import UnscoreableTrialError
from skillevolbench.schemas import RunConfig, StrategyConfig


REPO_ROOT = Path(__file__).resolve().parents[1]


def _config(tmp_path: Path, *, max_tasks: int | None = None) -> RunConfig:
    return RunConfig(
        run_id="ap-test",
        baseline=load_baseline("selfgen_experience_always"),
        strategy=StrategyConfig.from_yaml(
            REPO_ROOT / "configs" / "strategies" / "chain.yaml"
        ),
        environment_id="E1",
        workspace_root=tmp_path,
        max_tasks=max_tasks,
    )


def _report(
    *,
    evaluation_sr: float = 1.0,
    n_primary_trials: int = 30,
    n_replay_trials: int = 15,
    n_shadow_trials: int = 0,
) -> SimpleNamespace:
    return SimpleNamespace(
        task_success={
            "evaluation_sr": evaluation_sr,
            "learning_sr": 0.6,
            "t4_transfer": 0.7,
            "t5_trap_resistance": 0.8,
            "t6_composition_rate": 0.9,
        },
        evolution_replay={
            "evolution_lift": 0.2,
            "recovery_rate": 0.5,
            "regression_rate": 0.1,
            "fail_to_success_count": 3,
            "success_to_fail_count": 1,
        },
        revision_safety={
            "n_cross_task_revision_pairs": 12,
            "fail_to_success_count": 4,
            "fail_to_fail_count": 2,
            "success_to_success_count": 5,
            "success_to_fail_count": 1,
            "failure_recovery_rate": 2 / 3,
            "success_regression_rate": 1 / 6,
        },
        n_primary_trials=n_primary_trials,
        n_replay_trials=n_replay_trials,
        n_shadow_trials=n_shadow_trials,
    )


def test_complete_episode_metrics_are_scoreable(tmp_path: Path) -> None:
    metrics = run_episode._success_metrics(_config(tmp_path), _report())

    assert metrics["status"] == "completed"
    assert metrics["scoreable"] is True
    assert metrics["task_score"] == 1.0
    assert metrics["passed"] is True
    assert metrics["n_primary_trials"] == 30
    assert metrics["n_replay_trials"] == 15
    assert metrics["n_verifier_backed_trials"] == 45
    assert metrics["recovery_rate"] == 0.5
    assert metrics["cross_task_revision_pairs"] == 12
    assert metrics["cross_task_fail_to_success_count"] == 4
    assert metrics["cross_task_success_to_fail_count"] == 1
    assert metrics["cross_task_failure_recovery_rate"] == pytest.approx(2 / 3)
    assert metrics["cross_task_success_regression_rate"] == pytest.approx(1 / 6)
    assert "message" not in metrics


@pytest.mark.parametrize(
    ("config_max_tasks", "primary_trials", "replay_trials"),
    [
        (1, 30, 15),
        (None, 29, 15),
        (None, 30, 14),
    ],
)
def test_partial_episode_metrics_are_never_scoreable(
    tmp_path: Path,
    config_max_tasks: int | None,
    primary_trials: int,
    replay_trials: int,
) -> None:
    metrics = run_episode._success_metrics(
        _config(tmp_path, max_tasks=config_max_tasks),
        _report(
            evaluation_sr=1.0,
            n_primary_trials=primary_trials,
            n_replay_trials=replay_trials,
        ),
    )

    assert metrics["status"] == "partial"
    assert metrics["scoreable"] is False
    assert metrics["task_score"] == 0.0
    assert metrics["passed"] is False
    assert "Partial infrastructure smoke" in metrics["message"]


def test_build_config_routes_codex_without_duplicate_api_base(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = load_baseline("selfgen_experience_always").model_copy(
        update={"agent_kwargs": {"api_base": "http://stale.example/v1"}}
    )
    monkeypatch.setattr(run_episode, "load_baseline", lambda _name: baseline)
    monkeypatch.setenv("INSTANCE_ID", "E2")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1/")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("HARBOR_AGENT", "codex")
    monkeypatch.delenv("CODEX_WIRE_API", raising=False)

    config = run_episode._build_config(tmp_path)

    assert config.api_base is None
    assert config.baseline.harbor_agent_name == "codex"
    assert config.baseline.agent_kwargs == {
        "base_url": "http://model.example/v1",
        "provider": "sglang",
        "env_key": "OPENAI_API_KEY",
        "wire_api": "responses",
    }
    assert "api_base" not in config.baseline.agent_kwargs
    assert config.baseline.model_name == "openai/served-model"
    assert config.environment_id == "E2"
    assert config.workspace_root == (tmp_path / "runs").resolve()


def test_build_config_routes_opencode_via_chat_completions_without_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    baseline = load_baseline("selfgen_experience_always").model_copy(
        update={
            "agent_kwargs": {
                "api_base": "http://stale.example/v1",
                "wire_api": "responses",
            }
        }
    )
    monkeypatch.setattr(run_episode, "load_baseline", lambda _name: baseline)
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1/")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("MODEL_PROVIDER", "sglang")
    monkeypatch.setenv("OPENCODE_VERSION", "1.18.3")
    monkeypatch.delenv("HARBOR_AGENT", raising=False)

    config = run_episode._build_config(tmp_path)

    assert config.api_base is None
    assert config.baseline.harbor_agent_name == "opencode"
    assert config.baseline.model_name == "openai-compatible/served-model"
    assert config.baseline.agent_kwargs == {
        "version": "1.18.3",
        "opencode_config": {
            "$schema": "https://opencode.ai/config.json",
            "autoupdate": False,
            "snapshot": False,
            "permission": "allow",
            "provider": {
                "openai-compatible": {
                    "npm": "@ai-sdk/openai-compatible",
                    "name": "sglang",
                    "options": {
                        "baseURL": "{env:OPENAI_BASE_URL}",
                        "apiKey": "{env:OPENAI_API_KEY}",
                    },
                    "models": {
                        "served-model": {
                            "name": "served-model",
                            "attachment": False,
                            "limit": {"context": 131072, "output": 16384},
                        }
                    },
                }
            },
        },
    }
    assert "test-key" not in json.dumps(config.baseline.agent_kwargs)
    assert "stale.example" not in json.dumps(config.baseline.agent_kwargs)
    assert run_episode.os.environ["OPENAI_API_KEY"] == "test-key"
    assert run_episode.os.environ["OPENAI_BASE_URL"] == "http://model.example/v1"


def test_build_config_uses_absolute_dind_shared_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    shared_workspace = tmp_path / "dind-shared" / "runs"
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("SEVB_WORKSPACE_ROOT", str(shared_workspace))

    config = run_episode._build_config(tmp_path / "output")

    assert config.workspace_root == shared_workspace.resolve()


def test_build_config_rejects_relative_dind_shared_workspace(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("SEVB_WORKSPACE_ROOT", "relative/runs")

    with pytest.raises(ValueError, match="must be an absolute path"):
        run_episode._build_config(tmp_path)


def test_build_config_rejects_unsupported_agent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("HARBOR_AGENT", "claude-code")

    with pytest.raises(ValueError, match="supports HARBOR_AGENT='codex' or 'opencode'"):
        run_episode._build_config(tmp_path)


def test_build_config_rejects_global_library_scope(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    global_baseline = load_baseline("selfgen_experience_always").model_copy(
        update={"library_scope": "global"}
    )
    monkeypatch.setattr(run_episode, "load_baseline", lambda _name: global_baseline)
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")

    with pytest.raises(ValueError, match="global-scope baselines must run"):
        run_episode._build_config(tmp_path)


def test_mask_tree_redacts_env_values_and_keyed_credentials(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    json_path = tmp_path / "metrics.json"
    json_path.write_text(
        json.dumps(
            {
                "message": "request failed with model-secret-123",
                "api_key": "json-secret",
                "safe": "unchanged",
            }
        )
    )
    log_path = tmp_path / "episode.log"
    log_path.write_text(
        "Authorization: Bearer header-secret\n"
        "export AWS_SECRET_ACCESS_KEY=shell-secret\n"
    )
    ignored_path = tmp_path / "binary.bin"
    ignored_path.write_bytes(b"model-secret-123")

    assert mask_tree(tmp_path) == 2

    payload = json.loads(json_path.read_text())
    assert payload == {
        "message": "request failed with [REDACTED]",
        "api_key": "[REDACTED]",
        "safe": "unchanged",
    }
    assert log_path.read_text() == (
        "Authorization: Bearer [REDACTED]\n"
        "export AWS_SECRET_ACCESS_KEY=[REDACTED]\n"
    )
    assert ignored_path.read_bytes() == b"model-secret-123"


def test_sanitize_error_redacts_credentials(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "raw-secret")

    assert run_episode._sanitize_error("bad header raw-secret") == (
        "bad header [REDACTED]"
    )


def test_actionable_exception_unwraps_unscoreable_taskgroup_leaf() -> None:
    exception_group = getattr(builtins, "ExceptionGroup", None)
    if exception_group is None:
        pytest.skip("ExceptionGroup is only available on Python 3.11+")
    rejected = UnscoreableTrialError(
        "missing-verifier-result",
        task_id="E1-LS1-T1",
    )
    grouped = exception_group(
        "trial task group failed",
        [ValueError("noise"), rejected],
    )

    assert run_episode._actionable_exception(grouped) is rejected


def test_packaged_revision_file_takes_precedence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    revision = "a" * 40
    (tmp_path / ".skillevolbench-revision").write_text(f"{revision}\n")
    monkeypatch.setattr(run_episode, "REPO_ROOT", tmp_path)

    assert run_episode._safe_git_revision() == revision
