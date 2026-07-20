"""Report generator (Part 10 §13).

Aggregates every Part-10 metric module into a single :class:`FullReport`
that gets dumped to ``workspace/runs/<run_id>/reports/full_report.json``.

Schema bumped from ``"0.1-part9"`` to ``"1.0"`` in this version.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from skillevolbench.discovery import TaskRegistry
from skillevolbench.metrics.composition import compute_t6_composition
from skillevolbench.metrics.cost import compute_cost
from skillevolbench.metrics.evolution_replay import compute_evolution_replay
from skillevolbench.metrics.library_health import compute_library_health
from skillevolbench.metrics.retrieval_metrics import compute_retrieval_metrics
from skillevolbench.metrics.reflection_transfer import (
    compute_reflection_transfer,
)
from skillevolbench.metrics.revision_safety import compute_revision_safety
from skillevolbench.metrics.task_success import compute_task_success
from skillevolbench.metrics.transfer import compute_transfer
from skillevolbench.schemas import RunConfig
from skillevolbench.stores import (
    EventStore,
    LibraryStore,
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
    environment_id: Optional[str] = None
    n_tasks_attempted: int = 0
    n_primary_trials: int = 0
    n_replay_trials: int = 0
    n_shadow_trials: int = 0

    # Metric sections (stored as dicts so the schema doesn't need to track
    # every dataclass; loaders can re-parse via the dataclass functions).
    task_success: dict[str, Any] = Field(default_factory=dict)
    library_health: dict[str, Any] = Field(default_factory=dict)
    revision_safety: dict[str, Any] = Field(default_factory=dict)
    retrieval: dict[str, Any] = Field(default_factory=dict)
    t6_composition: dict[str, Any] = Field(default_factory=dict)
    transfer: dict[str, Any] = Field(default_factory=dict)
    evolution_replay: dict[str, Any] = Field(default_factory=dict)
    reflection: dict[str, Any] = Field(default_factory=dict)
    reflection_transfer: dict[str, Any] = Field(default_factory=dict)
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

    def _load_manifest_skills(self) -> list[Any]:
        """Load final skills from global or per-environment libraries.

        ``library_scope=environment`` stores independent repositories at
        ``library/E1`` ... ``library/E6``. The parent directory is not itself
        a ``LibraryStore`` and has no manifest, so treating it as one makes
        report generation fail after an otherwise successful run.
        """
        if not self.run_config.baseline.use_skill_library:
            return []

        lib_dir = self.run_root / "library"
        if not lib_dir.exists():
            return []

        scope = getattr(self.run_config.baseline, "library_scope", "global")
        if scope == "environment":
            roots = sorted(
                path
                for path in lib_dir.iterdir()
                if path.is_dir() and (path / "manifest.yaml").is_file()
            )
        else:
            roots = [lib_dir] if (lib_dir / "manifest.yaml").is_file() else []

        manifest_skills: list[Any] = []
        for root in roots:
            manifest_skills.extend(LibraryStore(root).list_all())
        return manifest_skills

    def generate(self) -> FullReport:
        replay = ReplayStore(self.run_root / "stores" / "replay")
        events = EventStore(self.run_root / "stores" / "events")

        # Library: aggregate all environment-scoped manifests when needed.
        manifest_skills = self._load_manifest_skills()
        library_skill_ids = {s.skill_id for s in manifest_skills}

        retrieval_dir = self.run_root / "stores" / "retrieval"
        retrieval = (
            RetrievalStore(retrieval_dir) if retrieval_dir.exists() else None
        )

        records = replay.all_records()
        primary_records = [
            record for record in records
            if getattr(record, "replay_mode", "primary") == "primary"
        ]
        replay_records = [
            record for record in records
            if getattr(record, "replay_mode", "primary") == "within_env_replay"
        ]
        shadow_records = [
            record for record in records
            if getattr(record, "replay_mode", "primary") == "shadow_oracle"
        ]
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
            replay_records=primary_records,
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
            replay_records=primary_records,
            retrieval_events=retrieval_events,
            library_skill_ids=library_skill_ids,
            task_specs=task_specs,
            task_compose_orders=task_orders,
            oracle_records=shadow_records or None,
        )

        # 6. Transfer
        original_records_by_task = {r.task_id: r for r in primary_records}
        retention_records = (
            self.retention_replay_records
            if self.retention_replay_records is not None
            else (replay_records or None)
        )
        transfer_section = compute_transfer(
            replay_records=primary_records,
            retention_replay_records=retention_records,
            original_records_by_task=original_records_by_task,
        )

        # 7. Paired original -> within-environment replay outcomes.
        evolution_section = compute_evolution_replay(records)

        # 8. Same-session reflection protocol. Invalid/noop candidates are
        # scoreable model outcomes; transport/session failures abort the run
        # earlier and therefore never masquerade as a terminal event here.
        reflection_events = {
            status: events.events_of_type(f"reflection_{status}")
            for status in ("completed", "noop", "rejected", "skipped")
        }
        terminal_events = [
            event
            for status_events in reflection_events.values()
            for event in status_events
        ]
        attempted_events = [
            event
            for status in ("completed", "noop", "rejected")
            for event in reflection_events[status]
        ]
        n_completed = len(reflection_events["completed"])
        n_noop = len(reflection_events["noop"])
        n_rejected = len(reflection_events["rejected"])
        n_attempted = len(attempted_events)

        def _same_session_verified(event: dict[str, Any]) -> bool:
            """Require the explicit host verdict and three matching IDs."""
            session_id = event.get("session_id")
            solve_session_id = event.get("solve_session_id")
            reflection_session_id = event.get("reflection_session_id")
            return (
                event.get("same_session_verified") is True
                and isinstance(session_id, str)
                and bool(session_id)
                and isinstance(solve_session_id, str)
                and bool(solve_session_id)
                and isinstance(reflection_session_id, str)
                and bool(reflection_session_id)
                and session_id == solve_session_id == reflection_session_id
            )

        reflection_section = {
            "enabled": (
                self.run_config.baseline.skill_update_source
                == "same_agent_session"
            ),
            "n_terminal": len(terminal_events),
            "n_attempted": n_attempted,
            "n_completed": n_completed,
            "n_noop": n_noop,
            "n_rejected": n_rejected,
            "n_skipped": len(reflection_events["skipped"]),
            "n_same_session_verified": sum(
                1 for event in attempted_events if _same_session_verified(event)
            ),
            # A deliberate no-op is a valid, parseable model output even
            # though it does not propose a patch. Keep output validity and
            # actionable patch production as separate metrics.
            "valid_output_rate": (
                (n_completed + n_noop) / n_attempted
                if n_attempted else None
            ),
            "patch_candidate_rate": (
                n_completed / n_attempted if n_attempted else None
            ),
            "noop_rate": (
                n_noop / n_attempted if n_attempted else None
            ),
            "rejection_rate": (
                n_rejected / n_attempted if n_attempted else None
            ),
        }

        # 9. Cross-task transfer after every terminal reflection outcome,
        # including no-op/rejected/skipped. This intentionally does not
        # condition on patch_applied.
        reflection_transfer_section = compute_reflection_transfer(
            primary_records
        )

        # 10. Cost
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
            environment_id=self.run_config.environment_id,
            n_tasks_attempted=len(records),
            n_primary_trials=len(primary_records),
            n_replay_trials=len(replay_records),
            n_shadow_trials=len(shadow_records),
            task_success=_to_dict(task_section),
            library_health=_to_dict(lib_section),
            revision_safety=_to_dict(rev_section),
            retrieval=_to_dict(retr_section),
            t6_composition=_to_dict(comp_section),
            transfer=_to_dict(transfer_section),
            evolution_replay=_to_dict(evolution_section),
            reflection=reflection_section,
            reflection_transfer=_to_dict(reflection_transfer_section),
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
