from __future__ import annotations

import json
import builtins
import hashlib
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.ap import run_episode
from scripts.ap.mask_secrets import SANITIZATION_MANIFEST, mask_tree
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


def _family_config(tmp_path: Path) -> RunConfig:
    return RunConfig(
        run_id="ap-family-smoke-test",
        baseline=load_baseline("selfgen_in_session_always"),
        strategy=StrategyConfig.from_yaml(
            REPO_ROOT / "configs" / "strategies" / "chain.yaml"
        ),
        environment_id="E1",
        family_smoke_id="E1-LS1",
        workspace_root=tmp_path,
    )


def _report(
    *,
    evaluation_sr: float = 1.0,
    n_primary_trials: int = 30,
    n_replay_trials: int = 15,
    n_shadow_trials: int = 0,
    reflection: dict[str, object] | None = None,
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
        reflection=reflection or {},
    )


def test_complete_episode_metrics_are_scoreable(tmp_path: Path) -> None:
    metrics = run_episode._success_metrics(_config(tmp_path), _report())

    assert metrics["status"] == "completed"
    assert metrics["scoreable"] is True
    assert metrics["task_score"] == 1.0
    assert metrics["passed"] is True
    assert metrics["n_primary_trials"] == 30
    assert metrics["expected_primary_trials"] == 30
    assert metrics["n_replay_trials"] == 15
    assert metrics["expected_replay_trials"] == 15
    assert metrics["n_verifier_backed_trials"] == 45
    assert metrics["expected_verifier_backed_trials"] == 45
    assert metrics["recovery_rate"] == 0.5
    assert metrics["cross_task_revision_pairs"] == 12
    assert metrics["cross_task_fail_to_success_count"] == 4
    assert metrics["cross_task_success_to_fail_count"] == 1
    assert metrics["cross_task_failure_recovery_rate"] == pytest.approx(2 / 3)
    assert metrics["cross_task_success_regression_rate"] == pytest.approx(1 / 6)
    assert "message" not in metrics


def test_complete_family_smoke_is_explicitly_noncanonical_and_unscoreable(
    tmp_path: Path,
) -> None:
    metrics = run_episode._success_metrics(
        _family_config(tmp_path),
        _report(
            evaluation_sr=1.0,
            n_primary_trials=6,
            n_replay_trials=0,
            reflection={
                "enabled": True,
                "n_terminal": 3,
                "n_attempted": 3,
                "n_completed": 1,
                "n_noop": 1,
                "n_rejected": 1,
                "n_agent_timeouts": 1,
                "n_same_session_verified": 3,
                "n_all_attempts_same_session_verified": 3,
                "learning_attempts_total": 7,
                "repair_attempts_total": 4,
                "initial_learning_pass_count": 1,
                "terminal_learning_pass_count": 2,
                "repaired_to_pass_count": 1,
                "same_task_repair_success_rate": 0.5,
                "valid_output_rate": 2 / 3,
                "patch_candidate_rate": 1 / 3,
                "noop_rate": 1 / 3,
                "rejection_rate": 1 / 3,
            },
        ),
    )

    assert metrics["execution_scope"] == "family_smoke"
    assert metrics["family_smoke_id"] == "E1-LS1"
    assert metrics["canonical"] is False
    assert metrics["status"] == "completed_noncanonical"
    assert metrics["scoreable"] is False
    assert metrics["passed"] is False
    assert metrics["task_score"] == 0.0
    assert metrics["n_primary_trials"] == 6
    assert metrics["expected_primary_trials"] == 6
    assert metrics["n_replay_trials"] == 0
    assert metrics["expected_replay_trials"] == 0
    assert metrics["n_reflection_expected"] == 3
    assert metrics["reflection_valid_output_rate"] == pytest.approx(2 / 3)
    assert metrics["reflection_patch_candidate_rate"] == pytest.approx(1 / 3)
    assert metrics["n_reflection_agent_timeouts"] == 1
    assert metrics["learning_attempts_total"] == 7
    assert metrics["repair_attempts_total"] == 4
    assert metrics["repaired_to_pass_count"] == 1
    assert metrics["same_task_repair_success_rate"] == 0.5
    assert "single-family smoke" in metrics["message"]


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


def test_build_config_replaces_generic_no_auth_placeholder(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "EMPTY")
    monkeypatch.setattr(run_episode.secrets, "token_hex", lambda size: "ab" * size)

    config = run_episode._build_config(tmp_path)

    runtime_key = "sevb-no-auth-" + "ab" * 24
    assert run_episode.os.environ["MODEL_API_KEY"] == runtime_key
    assert run_episode.os.environ["OPENAI_API_KEY"] == runtime_key
    assert runtime_key not in json.dumps(config.baseline.agent_kwargs)


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


def test_build_config_selects_explicit_t1_t6_family_smoke(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("SMOKE_FAMILY_ID", "E1-LS1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.delenv("SMOKE_MAX_TASKS", raising=False)
    monkeypatch.delenv("WITHIN_ENV_REPLAY", raising=False)
    monkeypatch.delenv("REPLAY_EVAL", raising=False)

    config = run_episode._build_config(tmp_path)

    assert config.environment_id == "E1"
    assert config.family_smoke_id == "E1-LS1"
    assert config.max_tasks is None
    assert config.baseline.within_env_replay is False
    assert config.baseline.replay_eval is False


def test_build_config_applies_bounded_same_session_attempt_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("LEARNING_MAX_ATTEMPTS", "3")

    config = run_episode._build_config(tmp_path)

    assert config.baseline.skill_update_source == "same_agent_session"
    assert config.baseline.learning_max_attempts == 3


def test_build_config_applies_bounded_agent_timeout_multiplier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("HARBOR_AGENT_TIMEOUT_MULTIPLIER", "2")

    config = run_episode._build_config(tmp_path)

    assert config.harbor_agent_timeout_multiplier == 2.0


@pytest.mark.parametrize("value", ["0.5", "5", "not-a-number"])
def test_build_config_rejects_invalid_agent_timeout_multiplier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("HARBOR_AGENT_TIMEOUT_MULTIPLIER", value)

    with pytest.raises(ValueError, match="HARBOR_AGENT_TIMEOUT_MULTIPLIER"):
        run_episode._build_config(tmp_path)


@pytest.mark.parametrize("value", ["0", "6", "not-an-int"])
def test_build_config_rejects_invalid_learning_attempt_budget(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("INSTANCE_ID", "E1")
    monkeypatch.setenv("MODEL", "served-model")
    monkeypatch.setenv("MODEL_BASE_URL", "http://model.example/v1")
    monkeypatch.setenv("MODEL_API_KEY", "test-key")
    monkeypatch.setenv("LEARNING_MAX_ATTEMPTS", value)

    with pytest.raises(ValueError, match="LEARNING_MAX_ATTEMPTS"):
        run_episode._build_config(tmp_path)


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
    ignored_path.write_bytes(b"\x00\xff")
    runtime_digests = {
        "episode.log": hashlib.sha256(log_path.read_bytes()).hexdigest(),
        "metrics.json": hashlib.sha256(json_path.read_bytes()).hexdigest(),
    }

    assert mask_tree(tmp_path) == 2

    payload = json.loads(json_path.read_text())
    assert payload == {
        "message": "request failed with [REDACTED]",
        "api_key": "[REDACTED]",
        "safe": "unchanged",
    }
    assert log_path.read_text() == (
        "Authorization: Bearer [REDACTED]\nexport AWS_SECRET_ACCESS_KEY=[REDACTED]\n"
    )
    assert ignored_path.read_bytes() == b"\x00\xff"

    manifest = json.loads((tmp_path / SANITIZATION_MANIFEST).read_text())
    assert manifest["schema_version"] == 1
    assert manifest["hash_algorithm"] == "sha256"
    assert manifest["scope"] == "changed-utf8-regular-files"
    assert manifest["excluded_mutable_paths"] == ["logs/main.log"]
    assert manifest["changed_file_count"] == 2
    assert [entry["path"] for entry in manifest["changed_files"]] == [
        "episode.log",
        "metrics.json",
    ]
    for entry in manifest["changed_files"]:
        delivered = (tmp_path / entry["path"]).read_bytes()
        assert entry["runtime_sha256"] == runtime_digests[entry["path"]]
        assert entry["delivered_sha256"] == hashlib.sha256(delivered).hexdigest()
        assert entry["runtime_size"] > entry["delivered_size"]
        assert entry["delivered_size"] == len(delivered)


def test_mask_tree_does_not_globally_replace_safe_placeholder_and_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "EMPTY")
    source = tmp_path / "trace.json"
    source.write_text(
        json.dumps(
            {
                "source": 'LEGACY_EMPTY_REGION = "EMPTY"',
                "api_key": "EMPTY",
            }
        )
    )
    before_sha256 = hashlib.sha256(source.read_bytes()).hexdigest()

    assert mask_tree(tmp_path) == 1
    assert json.loads(source.read_text()) == {
        "source": 'LEGACY_EMPTY_REGION = "EMPTY"',
        "api_key": "[REDACTED]",
    }

    manifest_path = tmp_path / SANITIZATION_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    assert manifest["changed_file_count"] == 1
    assert manifest["changed_files"] == [
        {
            "path": "trace.json",
            "runtime_sha256": before_sha256,
            "delivered_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
            "runtime_size": len(
                json.dumps(
                    {
                        "source": 'LEGACY_EMPTY_REGION = "EMPTY"',
                        "api_key": "EMPTY",
                    }
                ).encode()
            ),
            "delivered_size": len(source.read_bytes()),
        }
    ]
    manifest_bytes = manifest_path.read_bytes()

    assert mask_tree(tmp_path) == 0
    assert manifest_path.read_bytes() == manifest_bytes


def test_mask_tree_rejects_symlinks_outside_artifact_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    outside = tmp_path.parent / "outside.log"
    outside.write_text("model-secret-123\n")
    (tmp_path / "linked.log").symlink_to(outside)

    with pytest.raises(RuntimeError, match="symlink outside output root"):
        mask_tree(tmp_path)
    assert outside.read_text() == "model-secret-123\n"


def test_mask_tree_rejects_secret_in_symlink_target(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    (tmp_path / "harmless-link").symlink_to("model-secret-123")

    with pytest.raises(RuntimeError, match="symlink target contains"):
        mask_tree(tmp_path)


def test_mask_tree_allows_internal_symlinks_without_following_them(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    target = tmp_path / "target.log"
    target.write_text("model-secret-123\n")
    (tmp_path / "linked.log").symlink_to(target.name)

    assert mask_tree(tmp_path) == 1
    assert target.read_text() == "[REDACTED]\n"
    assert (tmp_path / "linked.log").is_symlink()


def test_mask_tree_manifest_seals_tree_against_later_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    first = tmp_path / "first.log"
    first.write_text("model-secret-123\n")

    assert mask_tree(tmp_path) == 1
    manifest_path = tmp_path / SANITIZATION_MANIFEST
    manifest_bytes = manifest_path.read_bytes()

    second = tmp_path / "second.log"
    second.write_text("model-secret-123\n")
    with pytest.raises(RuntimeError, match="already seals"):
        mask_tree(tmp_path)

    assert manifest_path.read_bytes() == manifest_bytes
    assert second.read_text() == "model-secret-123\n"


def test_mask_tree_excludes_active_platform_log_from_digest_inventory(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    main_log = tmp_path / "logs" / "main.log"
    main_log.parent.mkdir()
    main_log.write_text("model-secret-123\n")
    active_writer = main_log.open("a")
    original_inode = main_log.stat().st_ino

    try:
        assert mask_tree(tmp_path) == 1
        assert main_log.stat().st_ino != original_inode
        active_writer.write("model-secret-123 appended after snapshot\n")
        active_writer.flush()
    finally:
        active_writer.close()
    assert main_log.read_text() == "[REDACTED]\n"
    manifest = json.loads((tmp_path / SANITIZATION_MANIFEST).read_text())
    assert manifest["changed_file_count"] == 0
    assert manifest["changed_files"] == []

    with main_log.open("a") as stream:
        stream.write("finalizer completed\n")
    assert mask_tree(tmp_path) == 0


def test_mask_tree_rejects_manifest_with_tampered_size(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    artifact = tmp_path / "trace.json"
    artifact.write_text('{"api_key":"model-secret-123"}\n')
    assert mask_tree(tmp_path) == 1

    manifest_path = tmp_path / SANITIZATION_MANIFEST
    manifest = json.loads(manifest_path.read_text())
    manifest["changed_files"][0]["delivered_size"] += 1
    manifest_path.write_text(json.dumps(manifest))

    with pytest.raises(RuntimeError, match="digest mismatch"):
        mask_tree(tmp_path)


def test_mask_tree_rejects_non_utf8_supported_artifact(
    tmp_path: Path,
) -> None:
    (tmp_path / "broken.log").write_bytes(b"\xff")

    with pytest.raises(RuntimeError, match="cannot sanitize text artifact"):
        mask_tree(tmp_path)
    assert not (tmp_path / SANITIZATION_MANIFEST).exists()


def test_mask_tree_rejects_symlinked_root(tmp_path: Path) -> None:
    real_root = tmp_path / "real"
    real_root.mkdir()
    linked_root = tmp_path / "linked"
    linked_root.symlink_to(real_root, target_is_directory=True)

    with pytest.raises(RuntimeError, match="must be a real directory"):
        mask_tree(linked_root)


def test_mask_tree_replacements_do_not_cascade(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "long-secret")
    monkeypatch.setenv("OPENAI_API_KEY", "DACT")
    artifact = tmp_path / "trace.log"
    artifact.write_text("long-secret DACT\n")

    assert mask_tree(tmp_path) == 1
    assert artifact.read_text() == "[REDACTED] [REDACTED]\n"


def test_mask_tree_rejects_short_non_placeholder_secret(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "abc")
    artifact = tmp_path / "trace.log"
    artifact.write_text("abc\n")

    with pytest.raises(RuntimeError, match="MODEL_API_KEY"):
        mask_tree(tmp_path)
    assert artifact.read_text() == "abc\n"
    assert not (tmp_path / SANITIZATION_MANIFEST).exists()


def test_mask_tree_masks_exact_secret_in_source_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    source = tmp_path / "example.py"
    source.write_text('TOKEN = "model-secret-123"\n')

    assert mask_tree(tmp_path) == 1
    assert source.read_text() == 'TOKEN = "[REDACTED]"\n'
    manifest = json.loads((tmp_path / SANITIZATION_MANIFEST).read_text())
    assert [entry["path"] for entry in manifest["changed_files"]] == ["example.py"]


def test_mask_tree_rejects_secret_in_non_utf8_artifact(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("MODEL_API_KEY", "model-secret-123")
    binary = tmp_path / "payload.bin"
    binary.write_bytes(b"\xffmodel-secret-123\x00")

    with pytest.raises(RuntimeError, match="non-UTF-8 artifact"):
        mask_tree(tmp_path)
    assert not (tmp_path / SANITIZATION_MANIFEST).exists()


def test_mask_tree_rejects_nested_manifest_name(tmp_path: Path) -> None:
    nested = tmp_path / "nested" / SANITIZATION_MANIFEST
    nested.parent.mkdir()
    nested.write_text("not the root manifest\n")

    with pytest.raises(RuntimeError, match="nested sanitization manifest"):
        mask_tree(tmp_path)
    assert not (tmp_path / SANITIZATION_MANIFEST).exists()


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
