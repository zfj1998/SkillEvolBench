from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone


UTC = timezone.utc
US_TZ = timezone(timedelta(hours=-5))
EU_TZ = timezone(timedelta(hours=1))


def _build_order(order_id: int, created_at: str, region: str):
    return {"order_id": order_id, "created_at": created_at, "region": region}


BASE_TIME = datetime(2024, 1, 1, 22, 30, tzinfo=UTC)


def _regional_timestamp(order_id: int, tz):
    moment = BASE_TIME + timedelta(hours=order_id)
    return moment.astimezone(tz).isoformat()


SHARED = [
    _build_order(index, _regional_timestamp(index, UTC), "shared")
    for index in range(1, 21)
]
US_ONLY = [
    _build_order(index, _regional_timestamp(index, US_TZ), "us")
    for index in range(21, 81)
]
EU_ONLY = [
    _build_order(index, _regional_timestamp(index, EU_TZ), "eu")
    for index in range(81, 121)
]
REGIONAL_DATA = {
    "us": SHARED + US_ONLY,
    "eu": SHARED + EU_ONLY,
}


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)
    attempts: dict[tuple[str, int], int] = field(default_factory=dict)

    def fetch_orders(self, region: str, page: int = 1, per_page: int = 20):
        key = (region, page)
        self.attempts[key] = self.attempts.get(key, 0) + 1
        attempt = self.attempts[key]

        if region == "us" and page == 3 and attempt == 1:
            self.trace.append({
                "region": region,
                "page": page,
                "per_page": per_page,
                "attempt": attempt,
                "status": 503,
            })
            return {"status": 503, "error": "temporary unavailable"}

        rows = REGIONAL_DATA[region]
        start = (page - 1) * per_page
        end = start + per_page
        data = [{**item, "source_region": region} for item in rows[start:end]]
        has_more = end < len(rows)
        self.trace.append({
            "region": region,
            "page": page,
            "per_page": per_page,
            "attempt": attempt,
            "status": 200,
            "returned_ids": [item["order_id"] for item in data],
            "has_more": has_more,
        })
        return {"status": 200, "data": data, "has_more": has_more}

    def export_state(self):
        return {"trace": self.trace}


def build_api() -> MockAPI:
    return MockAPI()
