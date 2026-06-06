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
    "conversion_guard.py": dedent(
        """
        from __future__ import annotations


        def _safe_rate(numerator: float | int, impressions: float | int | None) -> float | None:
            if impressions is None or float(impressions) == 0.0:
                return None
            return round(float(numerator) / float(impressions), 6)


        def classify_status(impressions: float | int | None, audit: dict[str, int]) -> str:
            if impressions is None:
                return "data_missing"
            if float(impressions) == 0.0:
                return "no_traffic"
            if audit.get("missing_impression_rows", 0) or audit.get("invalid_impression_rows", 0):
                return "incomplete_data"
            return "active"


        def build_channel_metrics(
            *,
            channel: str,
            impressions: float | int | None,
            clicks: float | int,
            conversions: float | int,
            audit: dict[str, int],
        ) -> dict:
            return {
                "channel": channel,
                "impressions": impressions,
                "clicks": clicks,
                "conversions": conversions,
                "conversion_rate": _safe_rate(conversions, impressions),
                "ctr": _safe_rate(clicks, impressions),
                "status": classify_status(impressions, audit),
                "audit": audit,
            }
        """
    ),
}

for relative_path, content in FILES.items():
    target = PROJECT_ROOT / relative_path
    target.write_text(content, encoding="utf-8")
    print(f"wrote {target}")
__SKILL_EVOL_SOLVE_PY_0__
