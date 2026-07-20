"""SkillEvolBench CLI entry point.

The console script is registered in ``pyproject.toml`` as ``skillevolbench``.
Subcommands delegate to small modules in ``scripts/`` so the same operations
can also be invoked with ``python -m scripts.<name>``.

Subcommands:

* ``validate-assets``    -- validate benchmark tasks, skills, and runtime assets
* ``validate-configs``   -- validate yaml configs against Pydantic schemas
* ``dry-run-schedule``   -- print the canonical task order
* ``run``                -- launch one lifelong benchmark run
* ``summarize``          -- summarize one completed run
* ``launch-main``        -- launch the canonical baseline set
* ``launch-multi-model`` -- launch baseline x model sweeps
"""

from __future__ import annotations

import sys
from pathlib import Path

import click


def _ensure_repo_root_on_syspath() -> None:
    """Make lazy imports from ``scripts.*`` work under the console script."""
    here = Path(__file__).resolve()
    repo_root = here.parent.parent
    repo_root_str = str(repo_root)
    if repo_root_str not in sys.path:
        sys.path.insert(0, repo_root_str)


_ensure_repo_root_on_syspath()


@click.group(context_settings={"help_option_names": ["-h", "--help"]})
@click.version_option(package_name="skillevolbench")
def cli() -> None:
    """SkillEvolBench: lifelong skill evolution benchmark harness."""


@cli.command(name="validate-assets")
@click.option("--skills-root", type=click.Path(path_type=Path), default=None,
              help="override default benchmark/skills/")
@click.option("--tasks-root", type=click.Path(path_type=Path), default=None,
              help="override default benchmark/tasks/")
@click.option("--strict-image", is_flag=True,
              help="fail when agent-runtime:latest is not present")
def validate_assets_cmd(skills_root, tasks_root, strict_image):
    """Validate benchmark tasks, skills, and runtime assets."""
    from scripts.validate_assets import main as _main

    args: list[str] = []
    if skills_root is not None:
        args += ["--skills-root", str(skills_root)]
    if tasks_root is not None:
        args += ["--tasks-root", str(tasks_root)]
    if strict_image:
        args.append("--strict-image")
    raise SystemExit(_main(args))


@cli.command(name="validate-configs")
@click.option("--configs-root", type=click.Path(path_type=Path), default=None,
              help="override default configs/")
def validate_configs_cmd(configs_root):
    """Validate benchmark configuration files."""
    from scripts.validate_configs import main as _main

    args: list[str] = []
    if configs_root is not None:
        args += ["--configs-root", str(configs_root)]
    raise SystemExit(_main(args))


@cli.command(name="dry-run-schedule")
@click.option("--order-seed", default="A", type=click.Choice(["A", "B", "C"]))
@click.option("--environment-id", default=None,
              type=click.Choice([f"E{i}" for i in range(1, 7)]),
              help="show one complete environment episode")
@click.option("--show", default=10, type=int,
              help="how many head + tail tasks to display")
def dry_run_schedule_cmd(order_seed, environment_id, show):
    """Print the canonical task execution order."""
    from skillevolbench.discovery import (
        TaskRegistry, default_skills_root, default_tasks_root,
    )
    from skillevolbench.schemas import EnvOrders
    from skillevolbench.scheduler import compute_task_order, assert_order_invariants

    repo_root = Path(__file__).resolve().parent.parent
    registry = TaskRegistry.from_disk(default_skills_root(), default_tasks_root())
    env_orders = EnvOrders.from_yaml(repo_root / "configs" / "env_orders.yaml")
    order = compute_task_order(
        registry, env_orders, order_seed, environment_id=environment_id,
    )
    assert_order_invariants(
        order,
        expected_environment_ids=[environment_id] if environment_id else None,
    )

    click.echo(f"Order seed: {order_seed}")
    click.echo(f"Environment: {environment_id or 'all'}")
    click.echo(f"Total: {len(order)} tasks")
    click.echo()
    click.echo("Head:")
    for i, r in enumerate(order[:show]):
        click.echo(f"  {i + 1:3d}. {r.spec.task_id}  ({r.spec.role.value})")
    if len(order) > 2 * show:
        click.echo(f"  ... {len(order) - 2 * show} more ...")
    click.echo("Tail:")
    for i, r in enumerate(order[-show:], start=len(order) - show):
        click.echo(f"  {i + 1:3d}. {r.spec.task_id}  ({r.spec.role.value})")


@cli.command(name="run")
@click.option("--baseline", type=click.Path(path_type=Path), default=None,
              help="path to a baseline yaml (mutually exclusive with --baseline-name)")
@click.option("--baseline-name", default=None,
              help="canonical baseline name (e.g. 'no_skill')")
@click.option("--strategy", type=click.Path(path_type=Path), default=None,
              help="path to a strategy yaml (defaults to baseline.default_strategy)")
@click.option("--model-yaml", type=click.Path(path_type=Path), default=None,
              help="optional configs/models/*.yaml preset")
@click.option("--order-seed", default="A", type=click.Choice(["A", "B", "C"]))
@click.option("--environment-id", default=None,
              type=click.Choice([f"E{i}" for i in range(1, 7)]),
              help="run one complete environment episode (AP execution unit)")
@click.option("--run-id", default=None, help="override the auto-generated run_id")
@click.option("--workspace-root", type=click.Path(path_type=Path),
              default="workspace/runs",
              help="parent directory for run artifacts")
@click.option("--api-base", default=None)
@click.option("--api-key-env-var", default="ANTHROPIC_API_KEY")
@click.option("--dry-run", is_flag=True,
              help="run preflight + scheduler only")
@click.option("--max-tasks", default=None, type=click.IntRange(min=1),
              help="truncate to N trials for infrastructure smoke only")
@click.option("-v", "--verbose", is_flag=True)
def run_cmd(baseline, baseline_name, strategy, model_yaml, order_seed,
            environment_id, run_id, workspace_root, api_base,
            api_key_env_var, dry_run, max_tasks, verbose):
    """Launch one lifelong benchmark run."""
    from scripts.run import main as _main

    args: list[str] = []
    if baseline:
        args += ["--baseline", str(baseline)]
    if baseline_name:
        args += ["--baseline-name", baseline_name]
    if strategy:
        args += ["--strategy", str(strategy)]
    if model_yaml:
        args += ["--model-yaml", str(model_yaml)]
    args += ["--order-seed", order_seed]
    if environment_id:
        args += ["--environment-id", environment_id]
    if run_id:
        args += ["--run-id", run_id]
    args += ["--workspace-root", str(workspace_root)]
    if api_base:
        args += ["--api-base", api_base]
    args += ["--api-key-env-var", api_key_env_var]
    if dry_run:
        args.append("--dry-run")
    if max_tasks is not None:
        args += ["--max-tasks", str(max_tasks)]
    if verbose:
        args.append("-v")
    raise SystemExit(_main(args))


@cli.command(name="summarize")
@click.argument("run_dir", type=click.Path(path_type=Path, exists=True))
@click.option("--regenerate", is_flag=True,
              help="recompute report from on-disk stores")
@click.option("--json", "json_out", is_flag=True,
              help="emit JSON instead of the human summary")
def summarize_cmd(run_dir, regenerate, json_out):
    """Summarize a completed run."""
    from scripts.summarize import main as _main

    args = [str(run_dir)]
    if regenerate:
        args.append("--regenerate")
    if json_out:
        args.append("--json")
    raise SystemExit(_main(args))


@cli.command(name="launch-main")
@click.option("--order-seed", default="A", type=click.Choice(["A", "B", "C"]))
@click.option("--workspace-root", type=click.Path(path_type=Path),
              default="workspace/runs")
@click.option("--max-workers", default=4, type=int,
              help="how many runs to execute in parallel")
@click.option("--dry-run", is_flag=True,
              help="emit launch commands only")
@click.option("--baselines", default=None,
              help="comma-separated subset of canonical baseline names")
def launch_main_cmd(order_seed, workspace_root, max_workers, dry_run, baselines):
    """Launch the canonical baseline set."""
    from scripts.launch_main_experiment import main as _main

    args: list[str] = [
        "--order-seed", order_seed,
        "--workspace-root", str(workspace_root),
        "--max-workers", str(max_workers),
    ]
    if dry_run:
        args.append("--dry-run")
    if baselines:
        args += ["--baselines", baselines]
    raise SystemExit(_main(args))


@cli.command(name="launch-multi-model")
@click.option("--order-seed", default="A", type=click.Choice(["A", "B", "C"]))
@click.option("--workspace-root", type=click.Path(path_type=Path),
              default="workspace/runs")
@click.option("--max-workers", default=4, type=int,
              help="number of (baseline, model) runs in parallel")
@click.option("--baselines", default=None,
              help="comma-separated subset of canonical baselines")
@click.option("--models", default=None,
              help="comma-separated subset of configs/models/*.yaml stems")
@click.option("--dry-run", is_flag=True)
def launch_multi_model_cmd(order_seed, workspace_root, max_workers,
                            baselines, models, dry_run):
    """Cartesian launcher: baselines x model presets."""
    from scripts.launch_multi_model import main as _main

    args: list[str] = [
        "--order-seed", order_seed,
        "--workspace-root", str(workspace_root),
        "--max-workers", str(max_workers),
    ]
    if baselines:
        args += ["--baselines", baselines]
    if models:
        args += ["--models", models]
    if dry_run:
        args.append("--dry-run")
    raise SystemExit(_main(args))


def main() -> int:
    """Console-script entry point."""
    cli()
    return 0


if __name__ == "__main__":
    cli()
