from __future__ import annotations


class ReplayCache:
    def __init__(self) -> None:
        self._last_good_batch: list[dict] = []

    def observe(self, products: list[dict]) -> None:
        self._last_good_batch = [dict(item) for item in products]

    def last_good_batch(self) -> list[dict]:
        return [dict(item) for item in self._last_good_batch]
