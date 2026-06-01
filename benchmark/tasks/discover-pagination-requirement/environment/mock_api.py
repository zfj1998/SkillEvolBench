from __future__ import annotations

from dataclasses import dataclass, field


PRODUCTS = [
    {"id": index, "sku": f"sku-{index:03d}"}
    for index in range(1, 121)
]


@dataclass
class MockAPI:
    trace: list[dict] = field(default_factory=list)

    def get_products(self, page: int = 1, per_page: int = 25):
        start = (page - 1) * per_page
        end = start + per_page
        data = PRODUCTS[start:end]
        has_more = end < len(PRODUCTS)
        self.trace.append({
            "endpoint": "/products",
            "page": page,
            "per_page": per_page,
            "returned_ids": [item["id"] for item in data],
            "has_more": has_more,
            "total": len(PRODUCTS),
        })
        return {"data": data, "has_more": has_more, "total": len(PRODUCTS)}

    def export_state(self):
        return {"trace": self.trace}


def build_api() -> MockAPI:
    return MockAPI()
