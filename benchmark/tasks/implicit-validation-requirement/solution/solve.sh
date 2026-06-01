#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"
PYTHON_BIN="${PYTHON_BIN:-python3}"
"$PYTHON_BIN" - <<'__SKILL_EVOL_SOLVE_PY_0__'
from __future__ import annotations

import os
from pathlib import Path
from textwrap import dedent

PROJECT_ROOT = Path(os.environ.get("PROJECT_ROOT", "/root/task")).resolve()

FILES = {
    "transport_guard.py": dedent(
        """
        from __future__ import annotations


        def decode_payload(response, cache, logger):
            try:
                payload = response.json()
            except Exception:
                logger.warning("json parse failed, dropping response")
                return None

            data = payload.get("data")
            if not isinstance(data, list):
                logger.warning("response has no usable list payload")
                return None

            metadata = payload.get("metadata", {})
            if len(data) == 0:
                logger.info("empty page observed with batch_size=%s", metadata.get("batch_size"))
                return payload

            return payload
        """
    ),
    "inventory_cache.py": dedent(
        """
        from __future__ import annotations


        class LastGoodPayloadCache:
            def __init__(self) -> None:
                self._payload = None

            def observe(self, payload: dict) -> None:
                self._payload = payload

            def last_payload(self):
                return self._payload
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
