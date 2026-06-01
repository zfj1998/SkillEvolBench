from __future__ import annotations

import json
from collections import defaultdict
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
                differences = dict(difference)
                differences["record_id"] = merged["record_id"]
                conflicts.append(differences)
            for difference in deep_diff(base.get("compensation", {}), other.get("compensation", {}), "compensation"):
                differences = dict(difference)
                differences["record_id"] = merged["record_id"]
                conflicts.append(differences)

        master.append(merged)

    master.sort(key=lambda row: (row["name"], row.get("email", ""), row["record_id"]))
    (PROJECT_ROOT / "master_dataset.json").write_text(json.dumps(master, indent=2) + "\n", encoding="utf-8")
    (PROJECT_ROOT / "conflict_log.json").write_text(
        json.dumps(
            {
                "matching_method": "exact normalized email",
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
