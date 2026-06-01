"""Report generator (Part 10 §13).

Aggregates every Part-10 metric module into a single :class:`FullReport`
that gets dumped to ``workspace/runs/<run_id>/reports/full_report.json``.

Schema bumped from ``"0.1-part9"`` to ``"1.0"`` in this version.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from skillevolbench.discovery import TaskRegistry
from skillevolbench.metrics.composition import (
    T6CompositionReport,
    compute_t6_composition,
)
from skillevolbench.metrics.cost import CostReport, compute_cost
from skillevolbench.metrics.library_health import (
    LibraryHealthReport,
    compute_library_health,
)
from skillevolbench.metrics.retrieval_metrics import (
    RetrievalReport,
    compute_retrieval_metrics,
)
from skillevolbench.metrics.revision_safety import (
    RevisionSafetyReport,
    compute_revision_safety,
)
from skillevolbench.metrics.task_success import (
    TaskSuccessReport,
    compute_task_success,
)
from skillevolbench.metrics.transfer import TransferReport, compute_transfer
from skillevolbench.schemas import RunConfig
from skillevolbench.stores import (
    EventStore,
    LibraryStore,
    NullLibrary,
    ReplayStore,
    RetrievalStore,
)


# ---------------------------------------------------------------------------
# Pydantic wrappers for each metric report (so the FullReport JSON dump
# round-trips cleanly).
# ---------------------------------------------------------------------------


def _to_dict(obj: Any) -> dict[str, Any]:
    """Convert a dataclass-or-Pydantic-model to a plain dict.

    Pydantic v2 models expose ``model_dump``; dataclasses don't, but
    ``vars(obj)`` works for our flat dataclass shapes (no nested dataclasses
    except T6FailureTaxonomy, which we explicitly unfold).
    """
    if hasattr(obj, "model_dump"):
        return obj.model_dump(mode="json")
    if hasattr(obj, "__dataclass_fields__"):
        out: dict[str, Any] = {}
        for name in obj.__dataclass_fields__:
            v = getattr(obj, name)
            if hasattr(v, "__dataclass_fields__"):
                out[name] = _to_dict(v)
            elif isinstance(v, (list, tuple)):
                out[name] = [
                    _to_dict(x) if hasattr(x, "__dataclass_fields__") else x
                    for x in v
                ]
            elif isinstance(v, dict):
                out[name] = {
                    k: (_to_dict(x) if hasattr(x, "__dataclass_fields__") else x)
                    for k, x in v.items()
                }
            else:
                out[name] = v
        return out
    return obj


class FullReport(BaseModel):
    """Top-level run report (Part 10 schema_version 1.0)."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    schema_version: str = "1.0"
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    run_id: str
    baseline_name: str
    strategy_name: str
    order_seed: str
    n_tasks_attempted: int = 0

    # Metric sections (stored as dicts so the schema doesn't need to track
    # every dataclass; loaders can re-parse via the dataclass functions).
    task_success: dict[str, Any] = Field(default_factory=dict)
    library_health: dict[str, Any] = Field(default_factory=dict)
    revision_safety: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    t6_composition: dict[str, Any] = Field(default_factory=dict)
    transfer: dict[str, Any] = Field(default_factory=dict)
    cost: dict[str, Any] = Field(default_factory=dict)


# ---------------------------------------------------------------------------
# Generator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Builds a :class:`FullReport` from a completed run's directory."""

    def __init__(
        self,
        run_root: Path,
        run_config: RunConfig,
        *,
        task_registry: Optional[TaskRegistry] = None,
        retention_replay_records: Optional[list] = None,
        host_llm_clients: Optional[list] = None,
    ) -> None:
        self.run_root = Path(run_root)
        self.run_config = run_config
        self.task_registry = task_registry
        self.retention_replay_records = retention_replay_records
        # LiteLLMClient instances built by BaselineRuntime
        # (SkillAuthor / LLMSelfRetriever). Each has cumulative token
        # + per-tag counters that compute_cost reads at run end.
        self.host_llm_clients = host_llm_clients or []

    # ------------------------------------------------------------------
    # Main entry
    # ------------------------------------------------------------------

    def generate(self) -> FullReport:
        replay = ReplayStore(self.run_root / "stores" / "replay")
        events = EventStore(self.run_root / "stores" / "events")

        # Library: real or absent (control baselines).
        lib_dir = self.run_root / "library"
        if lib_dir.exists():
            library = LibraryStore(lib_dir)
            manifest_skills = list(library.list_all())
            library_skill_ids = {s.skill_id for s in manifest_skills}
        else:
            library = NullLibrary()
            manifest_skills = []
            library_skill_ids = set()

        retrieval_dir = self.run_root / "stores" / "retrieval"
        retrieval = (
            RetrievalStore(retrieval_dir) if retrieval_dir.exists() else None
        )

        records = replay.all_records()
        retrieval_events = retrieval.all_events() if retrieval else []

        # 1. Task success
        task_section = compute_task_success(records)

        # 2. Library health
        event_counts = {
            t: len(events.events_of_type(t))
            for t in (
                "patch_proposed", "patch_applied", "patch_rejected",
                "rollback_decision",
                "trial_ended_learning", "trial_ended_eval",
            )
        }
        lib_section = compute_library_health(
            manifest_skills=manifest_skills,
            replay_records=records,
            event_counts=event_counts,
            n_tasks_attempted=len(records),
        )

        # 3. Revision safety
        rev_section = compute_revision_safety(
            patch_events=events.all_events(channel="patches"),
            replay_records=records,
        )

        # 4. Retrieval
        retr_section = compute_retrieval_metrics(retrieval_events)

        # 5. T6 composition
        if self.task_registry is not None:
            task_specs = {
                t.spec.task_id: list(t.spec.required_skills)
                for t in self.task_registry.tasks
                if t.spec.role.value == "composition"
            }
            task_orders = {
                t.spec.task_id: list(t.spec.required_skill_compose_order)
                for t in self.task_registry.tasks
                if t.spec.role.value == "composition"
            }
        else:
            task_specs = {}
            task_orders = {}
        comp_section = compute_t6_composition(
            replay_records=records,
            retrieval_events=retrieval_events,
            library_skill_ids=library_skill_ids,
            task_specs=task_specs,
            task_compose_orders=task_orders,
        )

        # 6. Transfer
        original_records_by_task = {r.task_id: r for r in records}
        transfer_section = compute_transfer(
            replay_records=records,
            retention_replay_records=self.retention_replay_records,
            original_records_by_task=original_records_by_task,
        )

        # 7. Cost
        n_passed = sum(1 for r in records if r.outcome.verifier_passed)
        cost_section = compute_cost(
            event_counts=event_counts,
            n_tasks_attempted=len(records),
            n_tasks_passed=n_passed,
            evaluation_sr=task_section.evaluation_sr,
            replay_records=records,
            host_clients=self.host_llm_clients,
        )

        return FullReport(
            run_id=self.run_config.run_id,
            baseline_name=self.run_config.baseline.name,
            strategy_name=self.run_config.strategy.name,
            order_seed=self.run_config.order_seed,
            n_tasks_attempted=len(records),
            task_success=_to_dict(task_section),
            library_health=_to_dict(lib_section),
            revision_safety=_to_dict(rev_section),
            retrieval=_to_dict(retr_section),
            t6_composition=_to_dict(comp_section),
            transfer=_to_dict(transfer_section),
            cost=_to_dict(cost_section),
        )

    def write(self, report: FullReport) -> Path:
        target = self.run_root / "reports" / "full_report.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(report.model_dump_json(indent=2))
        return target

    @staticmethod
    def load(run_root: Path) -> FullReport:
        """Re-load a previously-written FullReport."""
        path = Path(run_root) / "reports" / "full_report.json"
        return FullReport.model_validate_json(path.read_text())


__all__ = ["FullReport", "ReportGenerator"]
