#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/entity_matcher.py" <<'__SKILL_EVOL_REFERENCE_ENTITY_MATCHER_PY_0__'
from __future__ import annotations

import re

NICKNAME_MAP = {
    "tom": "thomas",
    "rick": "richard",
    "bob": "robert",
    "bobby": "robert",
}


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def normalize_phone(value: str) -> str:
    digits = re.sub(r"\D", "", value or "")
    return digits[-7:] if digits else ""


def _tokens(name: str) -> list[str]:
    cleaned = (name or "").strip().lower()
    if "," in cleaned:
        left, right = [part.strip() for part in cleaned.split(",", 1)]
        cleaned = f"{right} {left}"
    return [token.strip(".") for token in cleaned.split() if token.strip(".")]


def _canonical_first(name: str) -> str:
    tokens = _tokens(name)
    if not tokens:
        return ""
    return NICKNAME_MAP.get(tokens[0], tokens[0])


def _last(name: str) -> str:
    tokens = _tokens(name)
    return tokens[-1] if tokens else ""


def same_entity(left: dict, right: dict) -> bool:
    left_email = normalize_email(left.get("email", ""))
    right_email = normalize_email(right.get("email", ""))
    if left_email and right_email and left_email == right_email:
        return True

    left_phone = normalize_phone(left.get("phone", ""))
    right_phone = normalize_phone(right.get("phone", ""))
    if left_phone and right_phone and left_phone == right_phone:
        return _last(left.get("name", "")) == _last(right.get("name", "")) and (
            _canonical_first(left.get("name", "")) == _canonical_first(right.get("name", ""))
            or _canonical_first(left.get("name", ""))[:1] == _canonical_first(right.get("name", ""))[:1]
        )

    return False
__SKILL_EVOL_REFERENCE_ENTITY_MATCHER_PY_0__
cat > "$PROJECT_ROOT/run_full_reconciliation.py" <<'__SKILL_EVOL_REFERENCE_RUN_FULL_RECONCILIATION_PY_0__'
from __future__ import annotations

import json
from pathlib import Path

from entity_matcher import same_entity
from nested_conflict_reporter import deep_diff
from resolution_policy import choose_value


PROJECT_ROOT = Path(__file__).resolve().parent


def normalize_record(source_name: str, record: dict) -> dict:
    if source_name == "system_a":
        return {
            "record_id": record["record_id"],
            "source": source_name,
            "name": record["name"],
            "email": record.get("email", ""),
            "phone": record.get("phone", ""),
            "department": record.get("department", ""),
            "address": record.get("address", {}),
            "compensation": record.get("compensation", {}),
        }
    if source_name == "system_b":
        return {
            "record_id": record["record_id"],
            "source": source_name,
            "name": record["name"],
            "email": record.get("email", ""),
            "phone": record.get("phone", ""),
            "department": record.get("dept", ""),
            "address": record.get("address", {}),
            "compensation": {"bonus": record.get("bonus_pct", "")},
        }
    return {
        "record_id": record["record_id"],
        "source": source_name,
        "name": record.get("full_name", ""),
        "email": record.get("email", ""),
        "phone": record.get("mobile", ""),
        "department": record.get("team", ""),
        "address": {"city": record.get("location", "")},
        "compensation": {},
    }


def cluster_records(records: list[dict]) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for record in records:
        matched = None
        for cluster in clusters:
            if any(same_entity(record, existing) for existing in cluster):
                matched = cluster
                break
        if matched is None:
            clusters.append([record])
        else:
            matched.append(record)
    return clusters


def main() -> None:
    raw_records = []
    for source_name in ("system_a", "system_b", "system_c"):
        raw = json.loads((PROJECT_ROOT / f"{source_name}.json").read_text(encoding="utf-8"))
        raw_records.extend(normalize_record(source_name, record) for record in raw)

    clusters = cluster_records(raw_records)
    master = []
    conflicts = []

    for cluster in clusters:
        merged = {"_sources": sorted({record["source"] for record in cluster}), "_record_ids": sorted({record["record_id"] for record in cluster})}
        for field_name in ("record_id", "name", "email", "phone", "department"):
            value, winner = choose_value(field_name, [(record["source"], record.get(field_name)) for record in cluster])
            merged[field_name] = value
            merged[f"_{field_name}_winner"] = winner

        address, _ = choose_value("address", [(record["source"], record.get("address", {})) for record in cluster])
        compensation, _ = choose_value("compensation", [(record["source"], record.get("compensation", {})) for record in cluster])
        merged["address"] = address
        merged["compensation"] = compensation

        base = cluster[0]
        for other in cluster[1:]:
            for difference in deep_diff(base.get("address", {}), other.get("address", {}), "address"):
                entry = dict(difference)
                entry["record_id"] = merged["record_id"]
                conflicts.append(entry)
            for difference in deep_diff(base.get("compensation", {}), other.get("compensation", {}), "compensation"):
                entry = dict(difference)
                entry["record_id"] = merged["record_id"]
                conflicts.append(entry)

        master.append(merged)

    master.sort(key=lambda row: (row["name"], row.get("email", ""), row["record_id"]))
    (PROJECT_ROOT / "master_dataset.json").write_text(json.dumps(master, indent=2) + "\n", encoding="utf-8")
    (PROJECT_ROOT / "conflict_log.json").write_text(
        json.dumps(
            {
                "matching_method": "normalized email with phone+nickname fallback",
                "resolution_strategy": "system_a > system_b > system_c",
                "total_conflicts": len(conflicts),
                "conflicts": conflicts,
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_RUN_FULL_RECONCILIATION_PY_0__

python3 "$PROJECT_ROOT/run_full_reconciliation.py"
