from __future__ import annotations


def bootstrap_token(api, clock) -> str:
    return api.issue_token(clock)["body"]["access_token"]


def refresh_token(api, clock) -> str:
    return api.issue_token(clock)["body"]["access_token"]
