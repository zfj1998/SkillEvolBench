from __future__ import annotations

from dataclasses import dataclass, field


DATA = [
    {"id": index, "name": f"user-{index:03d}"}
    for index in range(1, 101)
]


def _page(offset: int, limit: int):
    if offset == 40:
        return [DATA[39], *DATA[40:60]]
    return DATA[offset: offset + limit]


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)

    def fetch_users(self, offset: int = 0, limit: int = 20) -> dict:
        page = _page(offset, limit)
        response = {
            "data": page,
            "total": 100,
            "has_more": offset + limit < 100,
            "returned_count": len(page),
        }
        self.trace.append({
            "endpoint": "/users",
            "offset": offset,
            "limit": limit,
            "returned_ids": [item["id"] for item in page],
            "has_more": response["has_more"],
            "returned_count": len(page),
        })
        return response

    def export_state(self) -> dict:
        return {"trace": self.trace}


def build_api() -> MockAPI:
    return MockAPI()
