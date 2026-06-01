from __future__ import annotations

import uuid


def build_idempotency_key() -> str:
    return str(uuid.uuid4())
