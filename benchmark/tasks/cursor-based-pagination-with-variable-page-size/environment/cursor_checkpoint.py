from __future__ import annotations


def normalize_cursor(token: str | None):
    if token is None:
        return None
    # The legacy checkpoint store only persisted the stable cursor prefix and
    # dropped the service-managed size/snapshot suffix.
    return token.split("|", 1)[0]
