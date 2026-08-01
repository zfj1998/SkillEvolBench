from __future__ import annotations

import json
from pathlib import Path

import pytest

from skillevolbench.baselines import BaselineRuntime, load_baseline
from skillevolbench.discovery import (
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
)
from skillevolbench.harbor_ext.hooks import SkillEvolBenchHooks
from skillevolbench.orchestration import LifelongRunner
from skillevolbench.schemas import EnvOrders, RunConfig, StrategyConfig


REPO_ROOT = Path(__file__).resolve().parents[1]


def _strategy() -> StrategyConfig:
    return StrategyConfig.from_yaml(REPO_ROOT / "configs/strategies/chain.yaml")


def _curated_config(
    tmp_path: Path,
    *,
    oracle_skill_view: bool = True,
    shuffled_skill_view: bool = False,
) -> RunConfig:
    baseline = load_baseline("curated_static").model_copy(
        update={"retriever_type": "embedding"}
    )
    return RunConfig(
        run_id="oracle-t56-test",
        baseline=baseline,
        strategy=_strategy(),
        environment_id="E2",
        workspace_root=tmp_path,
        evaluation_only_t4_t6=True,
        oracle_skill_view=oracle_skill_view,
        shuffled_skill_view=shuffled_skill_view,
    )


def test_t4_t6_diagnostic_selects_exactly_fifteen_eval_tasks(
    tmp_path: Path,
) -> None:
    config = _curated_config(tmp_path)
    registry = TaskRegistry.from_disk(default_skills_root(), default_tasks_root())
    orders = EnvOrders.from_yaml(REPO_ROOT / "configs/env_orders.yaml")

    records = LifelongRunner(config)._compute_ordered_tasks(registry, orders)

    assert len(records) == 15
    assert {record.spec.environment_id for record in records} == {"E2"}
    assert {record.spec.task_index for record in records} == {4, 5, 6}
    assert len({record.spec.family_id for record in records}) == 5
    assert not any(record.is_replay for record in records)


def test_oracle_view_requires_curated_eval_only_baseline(tmp_path: Path) -> None:
    baseline = load_baseline("no_skill")
    with pytest.raises(ValueError, match="curated skill-library baseline"):
        RunConfig(
            run_id="invalid-oracle-view",
            baseline=baseline,
            strategy=_strategy(),
            environment_id="E2",
            workspace_root=tmp_path,
            evaluation_only_t4_t6=True,
            oracle_skill_view=True,
        )


def test_oracle_view_preseeds_five_gold_skills_and_projects_exact_subset(
    tmp_path: Path,
) -> None:
    config = _curated_config(tmp_path)
    registry = TaskRegistry.from_disk(default_skills_root(), default_tasks_root())
    runtime = BaselineRuntime.build(config)
    runtime.switch_env("E2")
    hooks = SkillEvolBenchHooks(
        runtime,
        registry,
        runtime.runtime_builder,
        runtime.prompt_builder,
    )

    hooks._seed_curated_environment("E2", "E2-LS1-T4")

    assert len(runtime.library.list_active()) == 5
    assert all(
        runtime.library.has_curated_for(f"E2-LS{index}") for index in range(1, 6)
    )

    t4 = registry.task("E2-LS1-T4").spec
    hooks._stage_oracle_skill_view(t4, t4.task_id)
    t4_audit = json.loads(
        (runtime.run_root / "oracle-skill-views/E2-LS1-T4.audit.json").read_text()
    )
    assert t4_audit["oracle_skill_ids"] == [t4.primary_skill]
    assert sorted(
        path.name
        for path in (runtime.run_root / "oracle-skill-views/E2-LS1-T4").iterdir()
    ) == [t4.primary_skill.split(".", 1)[1]]

    t6 = registry.task("E2-LS1-T6").spec
    hooks._stage_oracle_skill_view(t6, t6.task_id)
    t6_audit = json.loads(
        (runtime.run_root / "oracle-skill-views/E2-LS1-T6.audit.json").read_text()
    )
    assert t6_audit["oracle_skill_ids"] == t6.required_skills
    assert len(t6_audit["skills"]) == len(t6.required_skills) == 2
    assert all(len(skill["sha256"]) == 64 for skill in t6_audit["skills"])


def test_shuffled_view_preseeds_source_environment_and_is_disjoint(
    tmp_path: Path,
) -> None:
    config = _curated_config(
        tmp_path,
        oracle_skill_view=False,
        shuffled_skill_view=True,
    )
    registry = TaskRegistry.from_disk(default_skills_root(), default_tasks_root())
    runtime = BaselineRuntime.build(config)
    runtime.switch_env("E2")
    hooks = SkillEvolBenchHooks(
        runtime,
        registry,
        runtime.runtime_builder,
        runtime.prompt_builder,
    )

    hooks._seed_curated_environment("E2", "E2-LS1-T4")

    assert len(runtime.library.list_active()) == 10
    assert all(
        runtime.library.has_curated_for(f"{env_id}-LS{index}")
        for env_id in ("E2", "E3")
        for index in range(1, 6)
    )

    for task_id in ("E2-LS1-T4", "E2-LS1-T6"):
        task = registry.task(task_id).spec
        hooks._stage_shuffled_skill_view(task, task.task_id)
        audit = json.loads(
            (
                runtime.run_root / f"shuffled-skill-views/{task.task_id}.audit.json"
            ).read_text()
        )
        assert audit["condition"] == "shuffled_curated"
        assert audit["source_environment_id"] == "E3"
        assert len(audit["gold_skill_ids"]) == len(audit["shuffled_skill_ids"])
        assert set(audit["gold_skill_ids"]).isdisjoint(audit["shuffled_skill_ids"])
        expected_shuffled = {
            registry.family(
                f"E3-{gold_skill_id.split('.', 1)[0].split('-', 1)[1]}"
            ).meta.latent_skill_id
            for gold_skill_id in audit["gold_skill_ids"]
        }
        assert set(audit["shuffled_skill_ids"]) == expected_shuffled
        assert len(
            list((runtime.run_root / f"shuffled-skill-views/{task.task_id}").iterdir())
        ) == len(audit["gold_skill_ids"])


def test_oracle_and_shuffled_views_are_mutually_exclusive(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mutually exclusive"):
        _curated_config(
            tmp_path,
            oracle_skill_view=True,
            shuffled_skill_view=True,
        )
