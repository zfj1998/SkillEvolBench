from __future__ import annotations

from dataclasses import dataclass, field


BASE = [
    {"id": index, "order_number": f"order-{index:03d}"}
    for index in range(1, 101)
]
NEW_ITEMS = [
    {"id": index, "order_number": f"order-{index:03d}"}
    for index in range(101, 106)
]
CURSOR_PAGES = {
    None: (BASE[0:20], "cursor-1"),
    "cursor-1": (BASE[20:40], "cursor-2"),
    "cursor-2": (BASE[40:60], "cursor-3"),
    "cursor-3": (BASE[60:80], "cursor-4"),
    "cursor-4": (BASE[80:100], "cursor-5"),
    "cursor-5": (NEW_ITEMS, None),
}


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)
    offset_rows: list[dict] = field(default_factory=lambda: list(BASE))
    inserted: bool = False

    def _maybe_insert(self, trigger: bool) -> None:
        if not self.inserted and trigger:
            self.offset_rows = list(NEW_ITEMS) + self.offset_rows
            self.inserted = True

    def fetch_orders(self, offset=None, limit=20, cursor=None):
        # If no offset is provided, treat the request as cursor-mode even for the first page.
        if cursor is not None or offset is None:
            self._maybe_insert(cursor == "cursor-2")
            data, next_cursor = CURSOR_PAGES[cursor]
            response = {"data": data, "next_cursor": next_cursor, "total": 105}
            self.trace.append({
                "mode": "cursor",
                "cursor": cursor,
                "returned_ids": [item["id"] for item in data],
                "next_cursor": next_cursor,
                "total": response["total"],
                "inserted": self.inserted,
            })
            return response

        if offset is None:
            offset = 0
        self._maybe_insert(offset >= 40)
        data = self.offset_rows[offset: offset + limit]
        response = {
            "data": data,
            "total": len(self.offset_rows),
            "has_more": offset + limit < len(self.offset_rows),
        }
        self.trace.append({
            "mode": "offset",
            "offset": offset,
            "limit": limit,
            "returned_ids": [item["id"] for item in data],
            "total": response["total"],
            "inserted": self.inserted,
        })
        return response

    def export_state(self):
        return {"trace": self.trace, "inserted": self.inserted}


def build_api() -> MockAPI:
    return MockAPI()
