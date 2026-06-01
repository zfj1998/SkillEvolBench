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


class RateLimitAPI:
    def __init__(self, retry_after_by_case: dict[str, int]):
        self.retry_after_by_case = retry_after_by_case
        self.trace: list[dict[str, Any]] = []
        self.first_seen: dict[str, float] = {}

    def get_resource(self, case_id: str, clock: FakeClock) -> dict[str, Any]:
        required = self.retry_after_by_case[case_id]
        now = clock.time()
        first_seen = self.first_seen.setdefault(case_id, now)
        elapsed = now - first_seen
        if elapsed < required:
            response = {
                "status": 429,
                "headers": {"Retry-After": str(required)},
                "body": {"error": "rate_limited", "case_id": case_id},
            }
        else:
            response = {
                "status": 200,
                "headers": {},
                "body": {"case_id": case_id, "value": f"payload-{case_id}"},
            }
        self.trace.append(
            {
                "case_id": case_id,
                "timestamp": now,
                "status": response["status"],
                "retry_after": response["headers"].get("Retry-After"),
            }
        )
        return response
