from __future__ import annotations

from dataclasses import dataclass, field


EVENTS = [
    {"id": index, "event": f"evt-{index:03d}"}
    for index in range(1, 81)
]


def _page_for_cursor(cursor):
    """Return a page from opaque cursor state without publishing a static answer map."""
    if cursor is None:
        page_index = 0
        start = 0
    else:
        try:
            raw_index, raw_start = cursor.split("|", 1)
            page_index = int(raw_index.replace("cursor-", ""))
            start = int(raw_start)
        except (AttributeError, ValueError):
            raise ValueError(f"unknown cursor: {cursor}") from None

    page_sizes = (17, 12, 25, 14, 12)
    if not 0 <= page_index < len(page_sizes):
        raise ValueError(f"unknown cursor: {cursor}")
    size = page_sizes[page_index]
    data_start = max(0, start - 1) if page_index else start
    data = EVENTS[data_start:start + size]
    next_start = start + size
    if next_start >= len(EVENTS):
        next_cursor = None
    else:
        next_cursor = f"cursor-{page_index + 1}|{next_start}"
    return data, next_cursor


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)

    def fetch_events(self, cursor=None, **params):
        data, next_cursor = _page_for_cursor(cursor)
        self.trace.append({
            "endpoint": "/events",
            "cursor": cursor,
            "params": params,
            "returned_ids": [item["id"] for item in data],
            "next_cursor": next_cursor,
        })
        return {"data": data, "next_cursor": next_cursor}

    def export_state(self):
        return {"trace": self.trace, "total": 80}


def build_api() -> MockAPI:
    return MockAPI()
