"""
Domain models and validation helpers for the processing service.

All request / response shapes are defined here so that routes.py and
utils.py share a single source of truth for field names and constraints.
"""

from __future__ import annotations

import re
import time
import uuid
from dataclasses import asdict, dataclass, field
from typing import Any, Dict, List, Optional


# ---------------------------------------------------------------------------
# Request / Response Models
# ---------------------------------------------------------------------------

@dataclass
class ProcessingRequest:
    """Validated representation of an incoming /api/process payload."""
    source: str
    metrics: List[str]
    dimensions: List[str]
    filters: Dict[str, Any] = field(default_factory=dict)
    request_id: str = field(default_factory=lambda: uuid.uuid4().hex[:16])
    received_at: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class ProcessingResult:
    """Wrapper around a successful computation result."""
    request_id: str
    computation_id: str
    data: Dict[str, Any]
    cached: bool = False
    computed_at: float = field(default_factory=time.time)
    duration_ms: Optional[float] = None

    def to_response(self) -> dict:
        return {
            "request_id": self.request_id,
            "computation_id": self.computation_id,
            "data": self.data,
            "meta": {
                "cached": self.cached,
                "computed_at": self.computed_at,
                "duration_ms": self.duration_ms,
            },
        }


# ---------------------------------------------------------------------------
# Audit Log (persisted in-memory for demo; production uses Postgres)
# ---------------------------------------------------------------------------

@dataclass
class AuditEntry:
    event: str                              # "request" | "completion" | "error"
    computation_id: str
    timestamp: float = field(default_factory=time.time)
    detail: Optional[str] = None


class AuditLog:
    """Append-only in-memory audit trail.  Thread-safe for reads via copy."""

    _MAX_ENTRIES = 5000

    def __init__(self) -> None:
        self._entries: List[AuditEntry] = []

    def record(self, event: str, computation_id: str, detail: str | None = None) -> None:
        entry = AuditEntry(event=event, computation_id=computation_id, detail=detail)
        self._entries.append(entry)
        if len(self._entries) > self._MAX_ENTRIES:
            self._entries = self._entries[-self._MAX_ENTRIES:]

    def recent(self, n: int = 50) -> List[dict]:
        return [asdict(e) for e in self._entries[-n:]]

    @property
    def total(self) -> int:
        return len(self._entries)


# Module-level singleton
audit_log = AuditLog()


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

_VALID_SOURCE = re.compile(r"^[a-zA-Z][a-zA-Z0-9_-]{0,63}$")
_VALID_METRIC = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_.]{0,127}$")


def validate_processing_request(payload: dict) -> ProcessingRequest:
    """
    Validate raw JSON payload and return a ProcessingRequest.

    Raises ValueError with a human-readable message on any constraint
    violation so that routes.py can return a 400.
    """
    if not isinstance(payload, dict):
        raise ValueError("Payload must be a JSON object")

    source = payload.get("source")
    if not source or not isinstance(source, str):
        raise ValueError("'source' is required and must be a non-empty string")
    if not _VALID_SOURCE.match(source):
        raise ValueError(f"'source' contains invalid characters: {source!r}")

    metrics = payload.get("metrics")
    if not metrics or not isinstance(metrics, list):
        raise ValueError("'metrics' must be a non-empty list")
    for m in metrics:
        if not isinstance(m, str) or not _VALID_METRIC.match(m):
            raise ValueError(f"Invalid metric name: {m!r}")

    dimensions = payload.get("dimensions", [])
    if not isinstance(dimensions, list):
        raise ValueError("'dimensions' must be a list")

    filters = payload.get("filters", {})
    if not isinstance(filters, dict):
        raise ValueError("'filters' must be a JSON object")

    return ProcessingRequest(
        source=source,
        metrics=metrics,
        dimensions=dimensions,
        filters=filters,
    )
