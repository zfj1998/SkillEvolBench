from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class FakeClock:
    now: float = 0.0
    sleep_calls: list[float] = field(default_factory=list)

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleep_calls.append(seconds)
        self.now += seconds


class SequenceRng:
    def __init__(self, values: list[float]):
        self.values = values
        self.calls: list[dict[str, float]] = []
        self.index = 0

    def uniform(self, low: float, high: float) -> float:
        ratio = self.values[self.index % len(self.values)]
        self.index += 1
        value = low + (high - low) * ratio
        self.calls.append({"low": low, "high": high, "value": value})
        return value


class UnstableAPI:
    def __init__(self, failures_before_success: int = 3):
        self.failures_before_success = failures_before_success
        self.trace: list[dict[str, Any]] = []

    def get_payload(self, clock: FakeClock) -> dict[str, Any]:
        attempt = len(self.trace) + 1
        if attempt <= self.failures_before_success:
            response = {"status": 503, "body": {"error": "temporarily_unavailable", "attempt": attempt}}
        else:
            response = {"status": 200, "body": {"payload": "ready", "attempt": attempt}}
        self.trace.append({"attempt": attempt, "timestamp": clock.time(), "status": response["status"]})
        return response
