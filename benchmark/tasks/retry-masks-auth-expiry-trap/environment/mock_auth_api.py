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


class AuthAPI:
    def __init__(self, transient_503_remaining: int = 0, refresh_fail: bool = False):
        self.transient_503_remaining = transient_503_remaining
        self.refresh_fail = refresh_fail
        self.trace: list[dict[str, Any]] = []
        self.tokens: dict[str, float] = {}
        self.token_counter = 0

    def issue_token(self, clock: FakeClock) -> dict[str, Any]:
        self.trace.append({"op": "auth", "timestamp": clock.time()})
        if self.refresh_fail and self.token_counter >= 1:
            raise RuntimeError("refresh failed")
        self.token_counter += 1
        token = f"token-{self.token_counter}"
        self.tokens[token] = clock.time() + 1.0
        return {"status": 200, "body": {"access_token": token, "expires_at": self.tokens[token]}}

    def fetch_data(self, token: str, clock: FakeClock) -> dict[str, Any]:
        if token not in self.tokens or clock.time() >= self.tokens[token]:
            response = {"status": 401, "body": {"error": "token_expired"}}
        elif self.transient_503_remaining > 0:
            self.transient_503_remaining -= 1
            response = {"status": 503, "body": {"error": "temporarily_unavailable"}}
        else:
            response = {"status": 200, "body": {"data": "secret", "token": token}}
        self.trace.append({"op": "data", "timestamp": clock.time(), "token": token, "status": response["status"]})
        return response
