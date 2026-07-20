"""Top-level lifelong benchmark runner.

Pipeline::

    config -> validate assets/configs -> registry -> task_order -> runtime ->
    JobConfig -> harbor.Job -> hooks -> run -> finalize -> FullReport

Harbor imports live inside :meth:`LifelongRunner.run` so offline validators,
dry-runs, and report generation can run on machines without the SDK. The
runner records a benchmark tree hash before and after execution to catch
accidental asset drift.
"""

from __future__ import annotations

import hashlib
import json
import logging
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from skillevolbench.baselines import BaselineRuntime
from skillevolbench.discovery import (
    TaskRegistry,
    default_skills_root,
    default_tasks_root,
)
from skillevolbench.metrics.reporter import FullReport, ReportGenerator
from skillevolbench.scheduler import (
    assert_order_invariants,
    compute_task_order,
)
from skillevolbench.schemas import EnvOrders, RunConfig


_LOG = logging.getLogger(__name__)


class LifelongRunner:
    """Run one ``RunConfig`` end-to-end."""

    def __init__(
        self,
        config: RunConfig,
        *,
        env_orders_path: Optional[Path] = None,
        skills_root: Optional[Path] = None,
        tasks_root: Optional[Path] = None,
        # LLM injection (forwarded to BaselineRuntime.build).
        llm_author_call: Optional[Any] = None,
        # Deprecated compatibility alias for older tests/extensions.
        llm_patch_call: Optional[Any] = None,
        llm_judge_call: Optional[Any] = None,
        embedder: Optional[Any] = None,
    ) -> None:
        self.config = config
        self.env_orders_path = (
            env_orders_path
            or self._repo_root() / "configs" / "env_orders.yaml"
        )
        self.skills_root = skills_root or default_skills_root()
        self.tasks_root = tasks_root or default_tasks_root()
        self.llm_author_call = (
            llm_author_call if llm_author_call is not None else llm_patch_call
        )
        self.llm_judge_call = llm_judge_call
        self.embedder = embedder

    # ------------------------------------------------------------------
    # Public entrypoint
    # ------------------------------------------------------------------

    async def run(self) -> FullReport:
        """Full pipeline. Requires the Harbor SDK at call time."""
        # 1. Preflight (offline)
        self._preflight()
        registry = TaskRegistry.from_disk(self.skills_root, self.tasks_root)
        env_orders = EnvOrders.from_yaml(self.env_orders_path)
        ordered_tasks = self._compute_ordered_tasks(registry, env_orders)

        # 2. Build runtime
        runtime = BaselineRuntime.build(
            self.config,
            llm_author_call=self.llm_author_call,
            llm_judge_call=self.llm_judge_call,
            embedder=self.embedder,
        )
        run_root = runtime.run_root

        # 3. Persist run-config + benchmark hash for resume / audit
        self._persist_run_config(run_root)
        benchmark_hash = self._snapshot_benchmark_hash(run_root)

        # 4. Build Harbor JobConfig + register hooks
        # Harbor SDK is loaded only here -- module imports remain SDK-free.
        from harbor.job import Job  # type: ignore  # noqa: F401  -- runtime-only
        from skillevolbench.harbor_ext import SkillEvolBenchHooks
        from skillevolbench.harbor_ext._patches import apply_harbor_patches
        from skillevolbench.harbor_ext.job_builder import build_job_config

        # Patch ``Trial._execute_agent`` so on-disk ``instruction.md``
        # updates from our START hook actually reach the agent. Without
        # this every retrieval/history-augmented baseline silently runs
        # zero-shot. Idempotent; safe to call once per process.
        apply_harbor_patches()

        job_config = build_job_config(self.config, ordered_tasks)
        # Harbor 0.6+ deprecated direct ``Job(config=...)`` instantiation;
        # ``Job.create`` is the async classmethod that prepares the
        # task/metric registries before the Job becomes runnable.
        job = await Job.create(job_config)

        hooks = SkillEvolBenchHooks(
            runtime=runtime,
            task_registry=registry,
            runtime_builder=runtime.runtime_builder,
            prompt_builder=runtime.prompt_builder,
        )
        job.on_trial_started(hooks.on_trial_started)
        job.on_trial_ended(hooks.on_trial_ended)

        runtime.event_store.record(
            "run_started",
            {
                "run_id": self.config.run_id,
                "baseline": self.config.baseline.name,
                "strategy": self.config.strategy.name,
                "order_seed": self.config.order_seed,
                "benchmark_hash": benchmark_hash,
                "n_tasks": len(ordered_tasks),
            },
        )

        # 5. Execute
        try:
            await job.run()
        finally:
            # 6. Finalise: clean up the last env (post-eval maintenance)
            #    + tag final library + assert benchmark unchanged.
            await self._finalise(runtime, hooks, benchmark_hash)

        # 7. Generate report (Part 10 schema 1.0; sections are dicts).
        report_gen = ReportGenerator(
            run_root, self.config,
            task_registry=registry,
            host_llm_clients=runtime.host_llm_clients,
        )
        report = report_gen.generate()
        report_path = report_gen.write(report)

        runtime.event_store.record(
            "run_finished",
            {
                "run_id": self.config.run_id,
                "report_path": str(report_path),
                "overall_sr": report.task_success.get("overall_sr", 0.0),
                "evaluation_sr": report.task_success.get("evaluation_sr", 0.0),
            },
        )
        return report

    # ------------------------------------------------------------------
    # Offline-only helpers (testable without Harbor)
    # ------------------------------------------------------------------

    def prepare(self) -> tuple[BaselineRuntime, list[Any], TaskRegistry]:
        """All the work LifelongRunner.run does *before* it imports Harbor.

        Returns (runtime, ordered_tasks, registry). Useful for tests +
        dry-run flows that don't actually want to launch Harbor.
        """
        self._preflight()
        registry = TaskRegistry.from_disk(self.skills_root, self.tasks_root)
        env_orders = EnvOrders.from_yaml(self.env_orders_path)
        ordered_tasks = self._compute_ordered_tasks(registry, env_orders)
        runtime = BaselineRuntime.build(
            self.config,
            llm_author_call=self.llm_author_call,
            llm_judge_call=self.llm_judge_call,
            embedder=self.embedder,
        )
        self._persist_run_config(runtime.run_root)
        self._snapshot_benchmark_hash(runtime.run_root)
        return runtime, ordered_tasks, registry

    def _compute_ordered_tasks(
        self,
        registry: TaskRegistry,
        env_orders: EnvOrders,
    ) -> list[Any]:
        """Compute and validate the full benchmark or one AP episode."""
        ordered_tasks = compute_task_order(
            registry,
            env_orders,
            self.config.order_seed,
            within_env_replay=getattr(
                self.config.baseline, "within_env_replay", False
            ),
            replay_eval=getattr(self.config.baseline, "replay_eval", False),
            environment_id=self.config.environment_id,
        )
        if self.config.max_tasks is None:
            expected_envs = (
                [self.config.environment_id]
                if self.config.environment_id is not None
                else None
            )
            assert_order_invariants(
                ordered_tasks,
                expected_environment_ids=expected_envs,
            )
            return ordered_tasks

        truncated = ordered_tasks[: self.config.max_tasks]
        _LOG.warning(
            "Truncated run: using the first %d task(s); skipping the "
            "complete-episode order invariant.",
            len(truncated),
        )
        return truncated

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _preflight(self) -> None:
        """Validate static + config layers before touching disk."""
        # Re-validate the assets to catch any drift between config-load and run.
        # Imports are lazy: the validators live in scripts/ which itself uses
        # repo-root imports.
        from scripts.validate_assets import validate_all_assets
        from scripts.validate_configs import validate_configs

        report = validate_all_assets(self.skills_root, self.tasks_root)
        if report.errors:
            raise RuntimeError(
                "Asset validation failed:\n  - " + "\n  - ".join(report.errors)
            )
        cfg_report = validate_configs(self._repo_root() / "configs")
        if cfg_report.errors:
            raise RuntimeError(
                "Config validation failed:\n  - " + "\n  - ".join(cfg_report.errors)
            )

        # Ensure run_dir doesn't already exist (no implicit overwrite).
        run_root = self.config.run_dir
        if run_root.exists() and any(run_root.iterdir()):
            raise FileExistsError(
                f"run_root {run_root} already exists and is non-empty. "
                f"Choose a different run_id, or rm the existing dir."
            )

    def _persist_run_config(self, run_root: Path) -> None:
        target = run_root / "config.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(self.config.model_dump_json(indent=2))

    def _snapshot_benchmark_hash(self, run_root: Path) -> str:
        """Hash the benchmark/ tree at run start; record for the audit log.

        We use a simple deterministic walk over file paths + sha256 of bytes.
        Cheap (a few hundred files), and proves that the benchmark wasn't
        mutated mid-run.
        """
        h = hashlib.sha256()
        bench_dir = self._repo_root() / "benchmark"
        for p in sorted(bench_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(bench_dir).as_posix()
            h.update(rel.encode("utf-8"))
            h.update(b"\0")
            try:
                h.update(p.read_bytes())
            except OSError:
                continue
            h.update(b"\0")
        digest = h.hexdigest()

        target = run_root / "benchmark_hash.txt"
        target.write_text(digest + "\n")
        return digest

    async def _finalise(
        self,
        runtime: BaselineRuntime,
        hooks: Any,
        benchmark_hash_at_start: str,
    ) -> None:
        # 1. Final env transition (if a partial env was last)
        try:
            if hooks._current_env is not None:
                # Final maintenance and snapshotting must finish before report
                # generation. Scheduling a background task here races the
                # reporter and can silently omit the last environment's state.
                await hooks._handle_env_transition(hooks._current_env, "END")
        except AssertionError:
            # Freeze/hash protocol violations invalidate the run. Never turn
            # them into a nominally successful AP score.
            raise
        except Exception as exc:  # best-effort cleanup for non-protocol errors.
            _LOG.warning("LifelongRunner finalise: env_transition failed: %s", exc)

        # 2. Tag final snapshot
        if runtime.snapshot_store is not None:
            try:
                runtime.snapshot_store.tag("final")
            except Exception as exc:
                _LOG.warning("LifelongRunner finalise: snapshot tag failed: %s", exc)

        # 3. Assert benchmark unchanged
        try:
            now_hash = self._snapshot_benchmark_hash(runtime.run_root.parent / "_check")
        except Exception:
            now_hash = ""
        # Re-hash without writing to a temp dir; do an in-place compare.
        re_hash = hashlib.sha256()
        bench_dir = self._repo_root() / "benchmark"
        for p in sorted(bench_dir.rglob("*")):
            if not p.is_file():
                continue
            rel = p.relative_to(bench_dir).as_posix()
            re_hash.update(rel.encode("utf-8"))
            re_hash.update(b"\0")
            try:
                re_hash.update(p.read_bytes())
            except OSError:
                continue
            re_hash.update(b"\0")
        if re_hash.hexdigest() != benchmark_hash_at_start:
            runtime.event_store.record(
                "benchmark_mutated_during_run",
                {
                    "before": benchmark_hash_at_start,
                    "after": re_hash.hexdigest(),
                },
            )
            _LOG.error(
                "FATAL: benchmark/ was mutated during run %s. Data invalid.",
                self.config.run_id,
            )

        # 4. Cleanup any temp directory we may have used
        check_dir = runtime.run_root.parent / "_check"
        if check_dir.exists():
            shutil.rmtree(check_dir, ignore_errors=True)

    # ------------------------------------------------------------------

    @staticmethod
    def _repo_root() -> Path:
        # Default repo root when paths aren't explicitly provided.
        here = Path(__file__).resolve().parent
        return here.parent.parent  # skillevolbench/orchestration -> repo


__all__ = ["LifelongRunner"]
