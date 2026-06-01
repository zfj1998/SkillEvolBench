from __future__ import annotations

from dataclasses import dataclass, field


REPORTS = [
    {"id": index, "report": f"report-{index:03d}"}
    for index in range(1, 81)
]


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)

    def get_reports(self, page: int = 1, per_page: int = 10):
        start = (page - 1) * per_page
        end = start + per_page
        data = REPORTS[start:end]
        total_pages = 5 if page <= 3 else 8
        has_more = page < 8
        self.trace.append({
            "endpoint": "/reports",
            "page": page,
            "per_page": per_page,
            "returned_ids": [item["id"] for item in data],
            "total_pages": total_pages,
            "has_more": has_more,
        })
        return {"data": data, "total_pages": total_pages, "has_more": has_more}

    def export_state(self):
        return {"trace": self.trace}


def build_api() -> MockAPI:
    return MockAPI()
