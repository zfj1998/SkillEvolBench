#!/bin/bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"

cat > "$PROJECT_ROOT/label_audit.py" <<'PY'
from __future__ import annotations


def label_source(source: dict) -> str:
    source_type = source.get("source_type", "")
    if source_type in {"vendor_doc", "vendor_community"}:
        return "vendor"
    if source_type == "independent_review":
        return "independent"
    return "mixed"
PY

cat > "$PROJECT_ROOT/board_pipeline.py" <<'PY'
from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path

from label_audit import label_source
from source_loader import load_sources

ROOT = Path(__file__).resolve().parent
OUTPUT = ROOT / "output"
OUTPUT.mkdir(exist_ok=True)


def derive_decision(sources: list[dict], labels: list[dict]) -> dict:
    label_by_id = {item["source_id"]: item["label"] for item in labels}
    counts = Counter(label_by_id.values())
    independent_by_vendor: dict[str, list[str]] = defaultdict(list)
    vendor_by_vendor: dict[str, int] = defaultdict(int)

    for source in sources:
        label = label_by_id[source["id"]]
        vendor = source.get("vendor", "unknown")
        if label == "independent":
            independent_by_vendor[vendor].append(source.get("notes", ""))
        elif label == "vendor":
            vendor_by_vendor[vendor] += 1

    independent_vendors = sorted(independent_by_vendor)
    if len(independent_vendors) >= 2:
        winner = "mixed"
    elif independent_vendors:
        winner = independent_vendors[0]
    else:
        winner = "insufficient_independent_evidence"

    basis = (
        f"{counts['vendor']} vendor sources and {counts['independent']} independent sources were separated. "
        f"Vendor material supports factual product and compliance claims for {sorted(vendor_by_vendor)}, "
        f"while independent reviews cover tradeoffs for {independent_vendors}; the board should treat the result as a split, evidence-weighted comparison."
    )
    return {"winner": winner, "basis": basis}


def main() -> None:
    sources = load_sources()
    labels = [{"source_id": source["id"], "label": label_source(source)} for source in sources]
    decision = derive_decision(sources, labels)
    report = {"labels": labels, "decision": decision}
    (OUTPUT / "board_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
PY
