from __future__ import annotations

import asyncio
from pathlib import Path
from types import SimpleNamespace

import pytest

from skillevolbench.baselines import load_baseline
from skillevolbench.discovery import (
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
)
from skillevolbench.metrics.reporter import ReportGenerator
from skillevolbench.orchestration import LifelongRunner
from skillevolbench.scheduler import assert_order_invariants, compute_task_order
from skillevolbench.schemas import EnvOrders, RunConfig, StrategyConfig
from skillevolbench.stores import LibraryStore


REPO_ROOT = Path(__file__).resolve().parents[1]
LEARNING_ROLES = {"canonical", "enriched", "variant"}
EVAL_ROLES = {"context-shift", "adversarial", "composition"}


@pytest.fixture(scope="module")
def registry() -> TaskRegistry:
    return TaskRegistry.from_disk(default_skills_root(), default_tasks_root())


@pytest.fixture(scope="module")
def env_orders() -> EnvOrders:
    return EnvOrders.from_yaml(REPO_ROOT / "configs" / "env_orders.yaml")


def _run_config(
    tmp_path: Path,
    *,
    run_id: str = "episode-test",
    environment_id: str | None = "E1",
) -> RunConfig:
    return RunConfig(
        run_id=run_id,
        baseline=load_baseline("selfgen_experience_always"),
        strategy=StrategyConfig.from_yaml(
            REPO_ROOT / "configs" / "strategies" / "chain.yaml"
        ),
        order_seed="A",
        environment_id=environment_id,
        workspace_root=tmp_path,
    )


@pytest.mark.parametrize("environment_id", [f"E{i}" for i in range(1, 7)])
def test_single_environment_episode_has_canonical_30_task_order(
    registry: TaskRegistry,
    env_orders: EnvOrders,
    environment_id: str,
) -> None:
    records = compute_task_order(
        registry,
        env_orders,
        "A",
        environment_id=environment_id,
    )

    assert len(records) == 30
    assert {record.spec.environment_id for record in records} == {environment_id}
    assert all(record.spec.role.value in LEARNING_ROLES for record in records[:15])
    assert all(record.spec.role.value in EVAL_ROLES for record in records[15:])
    assert len({record.spec.family_id for record in records}) == 5
    assert_order_invariants(
        records,
        expected_environment_ids=[environment_id],
    )


def test_single_environment_learning_replay_has_45_trials(
    registry: TaskRegistry,
    env_orders: EnvOrders,
) -> None:
    records = compute_task_order(
        registry,
        env_orders,
        "B",
        within_env_replay=True,
        environment_id="E4",
    )

    assert len(records) == 45
    assert not any(record.is_replay for record in records[:30])
    assert all(record.is_replay for record in records[30:])
    assert all(record.spec.role.value in LEARNING_ROLES for record in records[30:])
    assert_order_invariants(records, expected_environment_ids=["E4"])


def test_single_environment_full_replay_has_60_trials(
    registry: TaskRegistry,
    env_orders: EnvOrders,
) -> None:
    records = compute_task_order(
        registry,
        env_orders,
        "C",
        within_env_replay=True,
        replay_eval=True,
        environment_id="E6",
    )

    assert len(records) == 60
    assert sum(record.is_replay for record in records) == 30
    assert_order_invariants(records, expected_environment_ids=["E6"])


def test_environment_invariant_rejects_wrong_episode(
    registry: TaskRegistry,
    env_orders: EnvOrders,
) -> None:
    records = compute_task_order(
        registry,
        env_orders,
        "A",
        environment_id="E1",
    )
    with pytest.raises(AssertionError, match="Expected environments"):
        assert_order_invariants(records, expected_environment_ids=["E2"])


def test_reporter_aggregates_environment_scoped_libraries(
    tmp_path: Path,
    registry: TaskRegistry,
) -> None:
    config = _run_config(tmp_path, environment_id=None)
    run_root = config.run_dir

    for env_id in ("E1", "E2"):
        family = registry.families_in_env(env_id)[0]
        store = LibraryStore.init(run_root / "library" / env_id)
        store.inject_curated(
            skill_md_path=family.folder / family.meta.curated_skill_path,
            family_id=family.meta.family_id,
            latent_skill_id=family.meta.latent_skill_id,
            created_from_task=family.meta.task_ids[0],
        )

    report = ReportGenerator(
        run_root,
        config,
        task_registry=registry,
    ).generate()

    assert report.library_health["total_skill_count"] == 2
    assert report.library_health["active_skill_count"] == 2


def test_finalise_awaits_last_environment_transition(tmp_path: Path) -> None:
    config = _run_config(tmp_path)
    runner = LifelongRunner(config)
    run_root = config.run_dir
    run_root.mkdir(parents=True)
    benchmark_hash = runner._snapshot_benchmark_hash(run_root)
    call_order: list[str] = []

    class Hooks:
        _current_env = "E1"

        async def _handle_env_transition(self, previous: str, new: str) -> None:
            await asyncio.sleep(0)
            call_order.append(f"transition:{previous}:{new}")

    class Snapshot:
        def tag(self, name: str) -> None:
            call_order.append(f"tag:{name}")

    runtime = SimpleNamespace(
        run_root=run_root,
        snapshot_store=Snapshot(),
        event_store=SimpleNamespace(record=lambda *_args, **_kwargs: None),
    )

    asyncio.run(runner._finalise(runtime, Hooks(), benchmark_hash))

    assert call_order == ["transition:E1:END", "tag:final"]
