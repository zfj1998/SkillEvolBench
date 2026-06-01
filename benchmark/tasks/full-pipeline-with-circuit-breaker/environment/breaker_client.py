from __future__ import annotations

from breaker_metrics import snapshot_state
from breaker_state import BreakerState
from cooldown_policy import next_probe_time
from probe_gate import begin_probe, should_fail_fast, should_probe


class ResilientClient:
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"

    def __init__(self, service, failure_threshold=5, recovery_timeout=15.0):
        self.service = service
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._breaker = BreakerState(mode=self.CLOSED)
        self.state_history = []

    @property
    def state(self):
        return self._breaker.mode

    @property
    def failure_count(self):
        return self._breaker.failure_streak

    @property
    def next_probe_at(self):
        return self._breaker.next_probe_at

    def _trip_open(self, clock):
        self._breaker.mode = self.OPEN
        self._breaker.probe_in_flight = False
        self._breaker.next_probe_at = next_probe_time(
            clock.time(),
            self.recovery_timeout,
            success_budget=self._breaker.recent_success_budget,
        )
        self.state_history.append(snapshot_state(self._breaker))

    def get_resource(self, clock):
        now = clock.time()
        if should_fail_fast(self._breaker, now):
            return {"state": self.OPEN, "error": "circuit_open"}
        if should_probe(self._breaker, now):
            begin_probe(self._breaker)
        elif self.state == self.OPEN:
            if now < self.next_probe_at:
                return {"state": self.OPEN, "error": "circuit_open"}

        response = self.service.fetch(clock)
        status = response["status"]
        self._breaker.last_status = status
        if status == 200:
            self._breaker.failure_streak = 0
            self._breaker.recent_success_budget = min(self._breaker.recent_success_budget + 5.0, 10.0)
            if self.state == self.HALF_OPEN:
                self._breaker.probe_in_flight = False
                self.state_history.append(snapshot_state(self._breaker))
                return {"state": self.HALF_OPEN, "body": response["body"]}
            self._breaker.mode = self.CLOSED
            self.state_history.append(snapshot_state(self._breaker))
            return {"state": self.CLOSED, "body": response["body"]}

        if status == 503:
            if self.state == self.HALF_OPEN:
                self._breaker.recent_success_budget = 0.0
                self._trip_open(clock)
                return {"state": self.OPEN, "error": "downstream_unavailable"}
            self._breaker.failure_streak += 1
            if self._breaker.failure_streak >= self.failure_threshold:
                self._trip_open(clock)
                return {"state": self.OPEN, "error": "downstream_unavailable"}
            return {"state": self.CLOSED, "error": "downstream_unavailable"}

        return {"state": self.state, "error": f"unexpected status: {status}"}
