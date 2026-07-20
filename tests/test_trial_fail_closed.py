from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.components import UnscoreableTrialError, VerifierAdapter
from skillevolbench.discovery import (
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
)
from skillevolbench.harbor_ext.hooks import SkillEvolBenchHooks
from skillevolbench.strategies.base import NoOp


TASK_ID = "E1-LS1-T1"


def _trial_result(
    tmp_path: Path,
    *,
    reward_text: str | None = "0.0\n",
    rewards: dict[str, float] | None = None,
    exception_info: Any = None,
    trajectory: bool = True,
) -> SimpleNamespace:
    trial_dir = tmp_path / f"{TASK_ID}__abcdefg"
    verifier_dir = trial_dir / "verifier"
    verifier_dir.mkdir(parents=True)
    if reward_text is not None:
        (verifier_dir / "reward.txt").write_text(reward_text)
    if trajectory:
        agent_dir = trial_dir / "agent"
        agent_dir.mkdir()
        (agent_dir / "codex.txt").write_text("agent attempted the task\n")
    verifier_result = (
        None
        if rewards is None
        else SimpleNamespace(rewards=rewards)
    )
    return SimpleNamespace(
        task_name=TASK_ID,
        trial_name=f"{TASK_ID}__abcdefg",
        trial_uri=f"file://{trial_dir}",
        task_id=None,
        verifier_result=verifier_result,
        exception_info=exception_info,
        agent_result=None,
    )


def test_verifier_backed_zero_is_valid_failure_evidence(tmp_path: Path) -> None:
    outcome = VerifierAdapter().parse(
        _trial_result(tmp_path, rewards={"reward": 0.0})
    )

    assert outcome.reward == 0.0
    assert outcome.verifier_passed is False
    assert outcome.trajectory_path is not None


def test_normalized_reward_is_used_instead_of_first_mapping_value(
    tmp_path: Path,
) -> None:
    outcome = VerifierAdapter().parse(
        _trial_result(
            tmp_path,
            reward_text="0.25\n",
            rewards={"total_score": 25.0, "normalized_score": 0.25},
        )
    )

    assert outcome.reward == 0.25


def _write_atif(path: Path, *, session_id: str = "ses-test") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "schema_version": "ATIF-v1.7",
                "session_id": session_id,
                "agent": {
                    "name": "opencode",
                    "version": "1.18.3",
                    "model_name": "test-model",
                },
                "steps": [
                    {
                        "step_id": 1,
                        "source": "user",
                        "message": "solve this task",
                    },
                    {
                        "step_id": 2,
                        "source": "agent",
                        "message": "done",
                    },
                ],
            }
        )
    )


@pytest.mark.parametrize(
    "relative_path",
    [
        "artifacts/logs/agent/trajectory.json",
        "agent/trajectory.json",
    ],
)
def test_resolves_canonical_atif_in_harbor_layouts(
    tmp_path: Path,
    relative_path: str,
) -> None:
    result = _trial_result(
        tmp_path,
        rewards={"reward": 0.0},
        trajectory=False,
    )
    trial_dir = VerifierAdapter._path_from_uri_or_str(result.trial_uri)
    trajectory_path = trial_dir / relative_path
    _write_atif(trajectory_path)

    outcome = VerifierAdapter().parse(result)

    assert outcome.trajectory_path == trajectory_path


def test_manifest_and_arbitrary_json_are_not_trajectories(tmp_path: Path) -> None:
    result = _trial_result(
        tmp_path,
        rewards={"reward": 0.0},
        trajectory=False,
    )
    trial_dir = VerifierAdapter._path_from_uri_or_str(result.trial_uri)
    artifacts_dir = trial_dir / "artifacts"
    artifacts_dir.mkdir()
    (artifacts_dir / "manifest.json").write_text(
        '[{"source":"/logs/agent/trajectory.json","status":"failed"}]'
    )
    (artifacts_dir / "unrelated.json").write_text('{"events": [{"ok": true}]}')
    (artifacts_dir / "trajectory.json").write_text(
        '{"schema_version":"ATIF-v1.7","steps":[]}'
    )

    with pytest.raises(UnscoreableTrialError) as captured:
        VerifierAdapter().parse(result)

    assert captured.value.reason == "missing-agent-trajectory"


def test_valid_atif_cli_specific_filename_is_safe_fallback(tmp_path: Path) -> None:
    result = _trial_result(
        tmp_path,
        rewards={"reward": 0.0},
        trajectory=False,
    )
    trial_dir = VerifierAdapter._path_from_uri_or_str(result.trial_uri)
    trajectory_path = trial_dir / "agent" / "future-cli.trajectory.json"
    _write_atif(trajectory_path)

    outcome = VerifierAdapter().parse(result)

    assert outcome.trajectory_path == trajectory_path


@pytest.mark.parametrize(
    ("reward_text", "rewards", "trajectory", "reason"),
    [
        ("0.0\n", None, True, "missing-verifier-result"),
        ("0.0\n", {}, True, "missing-verifier-rewards"),
        (None, {"reward": 0.0}, True, "missing-canonical-reward-file"),
        ("nan\n", {"reward": 0.0}, True, "canonical-reward-out-of-range"),
        ("1.5\n", {"reward": 1.5}, True, "canonical-reward-out-of-range"),
        ("0.0\n", {"reward": 1.0}, True, "verifier-reward-mismatch"),
        ("0.0\n", {"reward": 0.0}, False, "missing-agent-trajectory"),
    ],
)
def test_unscoreable_trial_shapes_are_rejected(
    tmp_path: Path,
    reward_text: str | None,
    rewards: dict[str, float] | None,
    trajectory: bool,
    reason: str,
) -> None:
    result = _trial_result(
        tmp_path,
        reward_text=reward_text,
        rewards=rewards,
        trajectory=trajectory,
    )

    with pytest.raises(UnscoreableTrialError) as captured:
        VerifierAdapter().parse(result)

    assert captured.value.reason == reason


def test_agent_exception_is_rejected_without_leaking_message(tmp_path: Path) -> None:
    result = _trial_result(
        tmp_path,
        rewards={"reward": 0.0},
        exception_info=SimpleNamespace(
            exception_type="NonZeroAgentExitCodeError",
            exception_message="request contained super-secret-token",
        ),
    )

    with pytest.raises(UnscoreableTrialError) as captured:
        VerifierAdapter().parse(result)

    assert captured.value.reason == "agent-or-runtime-exception"
    assert "NonZeroAgentExitCodeError" in str(captured.value)
    assert "super-secret-token" not in str(captured.value)


class _CallRecorder:
    def __init__(self) -> None:
        self.records: list[Any] = []

    def persist(self, record: Any) -> None:
        self.records.append(record)


class _Strategy:
    name = "test-strategy"

    def __init__(self) -> None:
        self.calls = 0

    def decide(self, _ctx: Any) -> NoOp:
        self.calls += 1
        return NoOp(reason="test")


class _FreezeController:
    frozen = False

    def __init__(self) -> None:
        self.submissions = 0

    def submit_patch(self, **_kwargs: Any) -> None:
        self.submissions += 1

    def freeze(self, _env_id: str) -> None:
        self.frozen = True


class _Compactor:
    def compact(self, *_args: Any, **_kwargs: Any) -> SimpleNamespace:
        return SimpleNamespace(to_dict=lambda: {"text": "compact"})


def _hooks_runtime() -> tuple[SimpleNamespace, _CallRecorder, _Strategy, _FreezeController]:
    replay_store = _CallRecorder()
    strategy = _Strategy()
    freeze_ctrl = _FreezeController()
    runtime = SimpleNamespace(
        verifier_adapter=VerifierAdapter(),
        trajectory_extractor=SimpleNamespace(
            extract_skills_used=lambda *_args, **_kwargs: []
        ),
        compactor=_Compactor(),
        compactor_rough=_Compactor(),
        replay_store=replay_store,
        library=SimpleNamespace(compute_hash=lambda: "unchanged-library-hash"),
        strategy=strategy,
        freeze_ctrl=freeze_ctrl,
        baseline=load_baseline("selfgen_experience_always"),
        event_store=SimpleNamespace(record=lambda *_args, **_kwargs: None),
    )
    return runtime, replay_store, strategy, freeze_ctrl


@pytest.fixture(scope="module")
def registry() -> TaskRegistry:
    return TaskRegistry.from_disk(default_skills_root(), default_tasks_root())


def _prepared_hooks(
    runtime: SimpleNamespace,
    registry: TaskRegistry,
) -> SkillEvolBenchHooks:
    hooks = SkillEvolBenchHooks(runtime, registry, None, None)  # type: ignore[arg-type]
    hooks._pre_state_cache[TASK_ID] = {
        "library_hash": "unchanged-library-hash",
        "retrieval": None,
    }
    return hooks


def test_invalid_trial_cannot_reach_replay_strategy_or_patch(
    tmp_path: Path,
    registry: TaskRegistry,
) -> None:
    runtime, replay_store, strategy, freeze_ctrl = _hooks_runtime()
    hooks = _prepared_hooks(runtime, registry)
    result = _trial_result(
        tmp_path,
        rewards={"reward": 0.0},
        exception_info=SimpleNamespace(
            exception_type="NonZeroAgentExitCodeError",
            exception_message="do-not-persist-this",
        ),
    )
    event = SimpleNamespace(task_name=TASK_ID, result=result)

    with pytest.raises(UnscoreableTrialError):
        hooks._on_trial_ended_sync(event)

    assert replay_store.records == []
    assert strategy.calls == 0
    assert freeze_ctrl.submissions == 0


def test_verifier_backed_zero_reaches_learning_pipeline(
    tmp_path: Path,
    registry: TaskRegistry,
) -> None:
    runtime, replay_store, strategy, freeze_ctrl = _hooks_runtime()
    hooks = _prepared_hooks(runtime, registry)
    event = SimpleNamespace(
        task_name=TASK_ID,
        result=_trial_result(tmp_path, rewards={"reward": 0.0}),
    )

    hooks._on_trial_ended_sync(event)

    assert len(replay_store.records) == 1
    assert replay_store.records[0].outcome.reward == 0.0
    assert strategy.calls == 1
    assert freeze_ctrl.submissions == 0
