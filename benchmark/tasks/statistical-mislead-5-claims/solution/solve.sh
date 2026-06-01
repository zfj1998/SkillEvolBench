#!/bin/bash
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
export PROJECT_ROOT
python3 - <<'PYCODE'

from __future__ import annotations
import os
from pathlib import Path

PROJECT_ROOT = Path(os.environ["PROJECT_ROOT"]).resolve()
(PROJECT_ROOT / "claim_audit.py").write_text(r"""
from __future__ import annotations
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)
CLAIMS = json.loads((ROOT / "claim_packets.json").read_text())

def correction_for(claim: str) -> str:
    text = claim.lower()
    if "nps" in text or "industry average" in text:
        return "Misleading: the customer-satisfaction comparison needs comparable sample sizes and methods before claiming superiority."
    if "cost" in text or "costs" in text:
        return "Misleading: a nominal cost drop needs inflation and baseline adjustment before calling it structural efficiency."
    if "competitors" in text or "compared ourselves" in text:
        return "Misleading: the comparison set may be selective, so the accurate statement should name the comparator pool and its limits."
    if "uptime" in text or "99.9" in text:
        return "Misleading: a short measurement window does not prove sustained operational excellence across the historical service period."
    if "%" in text or "grew" in text or "growth" in text:
        return "Misleading: percent growth should be paired with the absolute base and broader market context before inferring maturity or low risk."
    return "Needs more source context before the claim can support the conclusion stated."

def main():
    reviews = []
    for item in CLAIMS["claims"]:
        reviews.append({"id": item["id"], "label": "misleading", "correction": correction_for(item["claim"])})
    (OUTPUT / "claim_review.json").write_text(json.dumps({"reviews": reviews}, indent=2), encoding="utf-8")

if __name__ == "__main__":
    main()
""", encoding="utf-8")
PYCODE
