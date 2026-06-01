from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class BreakerState:
    mode: str = "closed"
    failure_streak: int = 0
    next_probe_at: float = 0.0
    probe_in_flight: bool = False
    recent_success_budget: float = 0.0
    last_status: int | None = None
    transitions: list[dict[str, Any]] = field(default_factory=list)

