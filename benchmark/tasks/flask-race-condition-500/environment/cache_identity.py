"""
Helpers for request coalescing and cache-key identity.

The analytics dashboard often fires the same query several times while a card
is rendering. We coalesce identical requests into the same short pricing
window so downstream enrichment calls can share cache entries.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Dict


def canonicalize_payload(payload: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize only computation-relevant fields for cache identity.

    Route-layer metadata such as request ids or timestamps should not affect
    the cache key because repeated dashboard refreshes should land on the same
    entry while the upstream pricing window is still open.
    """
    return {
        "source": payload.get("source"),
        "metrics": list(payload.get("metrics", [])),
        "dimensions": list(payload.get("dimensions", [])),
        "filters": dict(payload.get("filters", {})),
    }


def hash_payload(payload: Dict[str, Any]) -> str:
    normalized = canonicalize_payload(payload)
    content_bytes = json.dumps(normalized, sort_keys=True, default=str).encode()
    return hashlib.sha256(content_bytes).hexdigest()[:16]
