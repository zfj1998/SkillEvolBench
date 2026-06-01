from __future__ import annotations


def build_sync_context(max_retries: int) -> dict:
    return {"max_retries": max_retries}
