from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass
class FakeClock:
    now: float = 0.0

    def time(self) -> float:
        return self.now

    def set(self, value: float) -> None:
        self.now = value


class DownstreamAPI:
    def __init__(self):
        self.trace: list[dict[str, Any]] = []

    def fetch(self, clock: FakeClock) -> dict[str, Any]:
        now = clock.time()
        if now < 5:
            response = {"status": 200, "body": {"value": f"ok-{int(now)}"}}
        elif now < 35:
            response = {"status": 503, "body": {"error": "downstream_unavailable"}}
        else:
            response = {"status": 200, "body": {"value": f"recovered-{int(now)}"}}
        self.trace.append({"timestamp": now, "status": response["status"]})
        return response
