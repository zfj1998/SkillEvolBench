"""CLI: regenerate or summarize a single run's FullReport.

Usage::

    # Print a human summary from a completed run dir:
    python -m scripts.summarize workspace/runs/<run_id>

    # Force-regenerate full_report.json from the on-disk stores:
    python -m scripts.summarize workspace/runs/<run_id> --regenerate

    # Emit JSON instead of the human table:
    python -m scripts.summarize workspace/runs/<run_id> --json
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.discovery import (
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
)
from skillevolbench.metrics import FullReport, ReportGenerator
from skillevolbench.schemas import RunConfig


def _load_or_regen(run_dir: Path, regenerate: bool) -> FullReport:
    config_path = run_dir / "config.json"
    if not config_path.exists():
        raise FileNotFoundError(
            f"{config_path} missing -- this directory was not produced by "
            f"LifelongRunner.run."
        )
    config = RunConfig.model_validate_json(config_path.read_text())

    report_path = run_dir / "reports" / "full_report.json"
    if regenerate or not report_path.exists():
        registry = TaskRegistry.from_disk(default_skills_root(), default_tasks_root())
        gen = ReportGenerator(run_dir, config, task_registry=registry)
        report = gen.generate()
        gen.write(report)
        return report
    return ReportGenerator.load(run_dir)


def _format_human(report: FullReport) -> str:
    """Render a multi-section human summary."""
    ts = report.task_success
    lh = report.library_health
    rs = report.revision_safety
    rt = report.retrieval
    t6 = report.t6_composition
    tr = report.transfer
    cost = report.cost

    out = [
        f"=== Run summary: {report.run_id} (schema_version={report.schema_version}) ===",
        f"  baseline:  {report.baseline_name}",
        f"  strategy:  {report.strategy_name}",
        f"  seed:      {report.order_seed}",
        f"  n_tasks:   {report.n_tasks_attempted}",
        "",
        "## Task success (Engineering Design §12.1)",
        f"  T1 (canonical)             {ts.get('t1_pass_rate', 0):.3f}",
        f"  T2 (enriched / Gap1)       {ts.get('t2_pass_rate', 0):.3f}",
        f"  T3 (variant / Gap2)        {ts.get('t3_pass_rate', 0):.3f}",
        f"  T4 (transfer)              {ts.get('t4_transfer', 0):.3f}",
        f"  T5 (adversarial)           {ts.get('t5_pass_rate', 0):.3f}",
        f"  T5 (trap-resistance)       {ts.get('t5_trap_resistance', 0):.3f}",
        f"  T6 (composition)           {ts.get('t6_composition_rate', 0):.3f}",
        f"  Learning SR                {ts.get('learning_sr', 0):.3f}",
        f"  Evaluation SR              {ts.get('evaluation_sr', 0):.3f}",
        f"  Overall SR                 {ts.get('overall_sr', 0):.3f}",
        "",
        "## Library health (Engineering Design §12.5)",
        f"  active_skill_count          {lh.get('active_skill_count', 0)}",
        f"  effective_skill_count       {lh.get('effective_skill_count', 0)}",
        f"  retired_skill_count         {lh.get('retired_skill_count', 0)}",
        f"  quarantined_skill_count     {lh.get('quarantined_skill_count', 0)}",
        f"  skill_inflation_rate        {lh.get('skill_inflation_rate', 0):.3f}",
        f"  consolidation_ratio         {lh.get('consolidation_ratio', 0):.3f}",
        f"  stale_rate                  {lh.get('stale_rate', 0):.3f}",
        f"  redundancy_rate             {lh.get('redundancy_rate', 0):.3f}",
        f"  conflict_count              {lh.get('conflict_count', 0)}",
        f"  harmful_retention_rate      {lh.get('harmful_retention_rate', 0):.3f}",
        f"  retirement_count            {lh.get('retirement_count', 0)}",
        "",
        "## Revision safety (Engineering Design §12.6)",
        f"  n_proposed                  {rs.get('n_proposed', 0)}",
        f"  n_applied                   {rs.get('n_applied', 0)}",
        f"  n_rollbacks                 {rs.get('n_rollbacks', 0)}",
        f"  acceptance_rate             {rs.get('revision_acceptance_rate', 0):.3f}",
        f"  rollback_rate               {rs.get('rollback_rate', 0):.3f}",
        f"  help_rate                   {rs.get('revision_help_rate', 0):.3f}",
        f"  hurt_rate                   {rs.get('revision_hurt_rate', 0):.3f}",
        f"  patch_overfitting_rate      {rs.get('patch_overfitting_rate', 0):.3f}",
        "",
        "## Retrieval (Engineering Design §12.3)",
        f"  n_events                    {rt.get('n_events', 0)}",
        f"  retrieval_coverage          {rt.get('retrieval_coverage', 0):.3f}",
        f"  required_skill_hit_rate     {rt.get('required_skill_hit_rate', 0):.3f}",
        f"  mean_precision_at_k         {rt.get('mean_precision_at_k') or 0:.3f}",
        f"  mean_recall_at_k            {rt.get('mean_recall_at_k') or 0:.3f}",
        f"  wrong_skill_rate            {rt.get('wrong_skill_rate', 0):.3f}",
        f"  cross_env_misretrieval      {rt.get('cross_env_misretrieval_rate', 0):.3f}",
        "",
        "## T6 composition (Engineering Design §12.4)",
        f"  n_t6                        {t6.get('n_t6', 0)}",
        f"  t6_pass_rate                {t6.get('t6_pass_rate', 0):.3f}",
        f"  required_skill_hit_rate     {t6.get('required_skill_hit_rate', 0):.3f}",
        f"  ordering_accuracy           {t6.get('composition_ordering_accuracy', 0):.3f}",
        "  failure taxonomy:",
    ]
    tax = t6.get("failure_taxonomy", {}) or {}
    for k, v in tax.items():
        if v:
            out.append(f"    - {k:30s} {v}")
    out += [
        "",
        "## Transfer (Engineering Design §12.7)",
        f"  cross_env_reuse_rate        {tr.get('cross_env_reuse_rate', 0):.3f}",
        f"  positive_transfer_rate      {tr.get('positive_transfer_rate', 0):.3f}",
        f"  negative_transfer_rate      {tr.get('negative_transfer_rate', 0):.3f}",
        f"  interference_rate           {tr.get('interference_rate', 0):.3f}",
    ]
    if tr.get("final_retention_rate") is not None:
        out += [
            f"  final_retention_rate        {tr['final_retention_rate']:.3f}",
            f"  forgetting_rate             {tr.get('forgetting_rate') or 0:.3f}",
        ]
    out += [
        "",
        "## Cost (Engineering Design §12.8)",
        f"  n_llm_calls_estimate        {cost.get('n_llm_calls_estimate', 0)}",
        f"  llm_calls_per_task          {cost.get('llm_calls_per_task', 0):.3f}",
        f"  cost_adjusted_evaluation_sr {cost.get('cost_adjusted_evaluation_sr', 0):.4f}",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run_dir", type=Path, help="path to workspace/runs/<run_id>/")
    p.add_argument(
        "--regenerate", action="store_true",
        help="recompute the report from on-disk stores even if reports/full_report.json exists"
    )
    p.add_argument("--json", action="store_true",
                   help="emit JSON instead of the human-readable summary")
    args = p.parse_args(argv)

    run_dir = Path(args.run_dir).resolve()
    if not run_dir.exists():
        raise SystemExit(f"run_dir does not exist: {run_dir}")

    report = _load_or_regen(run_dir, regenerate=args.regenerate)
    if args.json:
        print(report.model_dump_json(indent=2))
    else:
        print(_format_human(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
