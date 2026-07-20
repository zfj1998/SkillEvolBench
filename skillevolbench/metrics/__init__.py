"""Metrics and single-run reporting.

Each metric module exposes a compute function that consumes stores, replay
records, or event counts. ``ReportGenerator`` aggregates them into
``workspace/runs/<run_id>/reports/full_report.json``.
"""

from skillevolbench.metrics.composition import (
    T6CompositionReport,
    T6FailureTaxonomy,
    compute_t6_composition,
)
from skillevolbench.metrics.cost import CostReport, compute_cost
from skillevolbench.metrics.evolution_replay import (
    EvolutionReplayReport,
    compute_evolution_replay,
)
from skillevolbench.metrics.library_health import (
    LibraryHealthReport,
    compute_library_health,
)
from skillevolbench.metrics.reporter import FullReport, ReportGenerator
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


__all__ = [
    "FullReport",
    "ReportGenerator",
    "TaskSuccessReport",
    "LibraryHealthReport",
    "RevisionSafetyReport",
    "RetrievalReport",
    "T6CompositionReport",
    "T6FailureTaxonomy",
    "TransferReport",
    "CostReport",
    "EvolutionReplayReport",
    "compute_task_success",
    "compute_library_health",
    "compute_revision_safety",
    "compute_retrieval_metrics",
    "compute_t6_composition",
    "compute_transfer",
    "compute_cost",
    "compute_evolution_replay",
]
