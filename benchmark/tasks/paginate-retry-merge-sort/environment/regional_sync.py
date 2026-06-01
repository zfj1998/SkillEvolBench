from __future__ import annotations

from retry_policy import should_retry


def fetch_region(api, region: str) -> list[dict]:
    page = 1
    rows: list[dict] = []

    while True:
        attempt = 0
        while True:
            response = api.fetch_orders(region=region, page=page)
            if response["status"] == 200:
                break
            if not should_retry(response["status"], attempt):
                raise RuntimeError(f"failed to fetch {region} page {page}")
            attempt += 1

        rows.extend(response["data"])
        if not response["has_more"]:
            break
        page += 1

    return rows
