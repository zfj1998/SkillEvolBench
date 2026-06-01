from __future__ import annotations

from request_budget import wait_before_detail


def collect_details(api, items: list[dict[str, str]], session: dict[str, object]) -> list[dict]:
    headers = session["headers"]
    details = []
    for index, item in enumerate(items, start=1):
        wait_before_detail(index)
        details.append(api.get_item_detail(item["id"], headers))
    return details
