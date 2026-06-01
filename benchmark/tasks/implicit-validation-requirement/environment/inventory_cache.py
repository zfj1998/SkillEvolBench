from __future__ import annotations


class LastGoodPayloadCache:
    def __init__(self) -> None:
        self._payload: dict | None = None

    def observe(self, payload: dict) -> None:
        self._payload = payload

    def last_payload(self):
        return self._payload
