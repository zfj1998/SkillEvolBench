from __future__ import annotations


def project_page(response: dict) -> dict:
    return {
        "products": response["data"],
        "catalog_size": response["total"],
        "more_available": response["has_more"],
    }
