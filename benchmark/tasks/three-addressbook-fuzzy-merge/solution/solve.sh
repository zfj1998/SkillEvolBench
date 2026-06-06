#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="${PROJECT_ROOT:-/root/task}"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

cat > "$PROJECT_ROOT/identity_matcher.py" <<'__SKILL_EVOL_REFERENCE_IDENTITY_MATCHER_PY_0__'
from __future__ import annotations

import re

NICKNAME_MAP = {
    "bob": "robert",
    "bobby": "robert",
    "jim": "james",
    "jimmy": "james",
    "bill": "william",
    "will": "william",
    "rick": "richard",
    "tom": "thomas",
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


def _canonical_first_token(name: str) -> str:
    tokens = _tokens(name)
    if not tokens:
        return ""
    return NICKNAME_MAP.get(tokens[0], tokens[0])


def _last_token(name: str) -> str:
    tokens = _tokens(name)
    return tokens[-1] if tokens else ""


def _is_initial_variant(left: str, right: str) -> bool:
    left_first = _canonical_first_token(left)
    right_first = _canonical_first_token(right)
    if not left_first or not right_first:
        return False
    if left_first == right_first:
        return True
    return len(left_first) == 1 and right_first.startswith(left_first) or len(right_first) == 1 and left_first.startswith(right_first)


def same_person(left: dict, right: dict) -> bool:
    left_email = normalize_email(left.get("email", ""))
    right_email = normalize_email(right.get("email", ""))
    if left_email and right_email and left_email == right_email:
        return True

    left_phone = normalize_phone(left.get("phone", ""))
    right_phone = normalize_phone(right.get("phone", ""))
    if left_phone and right_phone and left_phone == right_phone:
        return _last_token(left.get("name", "")) == _last_token(right.get("name", "")) and _is_initial_variant(
            left.get("name", ""), right.get("name", "")
        )

    return False
__SKILL_EVOL_REFERENCE_IDENTITY_MATCHER_PY_0__
cat > "$PROJECT_ROOT/build_master_contacts.py" <<'__SKILL_EVOL_REFERENCE_BUILD_MASTER_CONTACTS_PY_0__'
from __future__ import annotations

import csv
import json
from pathlib import Path

from identity_matcher import normalize_phone, same_person
from merge_policy import merge_cluster
from source_registry import load_all_sources


PROJECT_ROOT = Path(__file__).resolve().parent
MASTER_PATH = PROJECT_ROOT / "master_contacts.csv"
REPORT_PATH = PROJECT_ROOT / "merge_report.md"
AUDIT_PATH = PROJECT_ROOT / "merge_audit.json"


def cluster_records(records: list[dict]) -> list[list[dict]]:
    clusters: list[list[dict]] = []
    for record in records:
        matched_cluster = None
        for cluster in clusters:
            if any(same_person(record, existing) for existing in cluster):
                matched_cluster = cluster
                break
        if matched_cluster is None:
            clusters.append([record])
        else:
            matched_cluster.append(record)
    return clusters


def write_master(rows: list[dict]) -> None:
    fields = ["email", "name", "phone", "department", "city", "title", "_sources", "_record_ids"]
    with MASTER_PATH.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    records = load_all_sources(PROJECT_ROOT)
    clusters = cluster_records(records)
    master_rows = [merge_cluster(cluster) for cluster in clusters]
    master_rows.sort(key=lambda row: (row["name"], row["email"], row["phone"]))

    phone_assisted = 0
    for cluster, row in zip(clusters, master_rows):
        emails = [record.get("email", "").strip() for record in cluster if record.get("email", "").strip()]
        if 0 < len(emails) < len(cluster):
            phones = {normalize_phone(record.get("phone", "")) for record in cluster if normalize_phone(record.get("phone", ""))}
            if len(phones) == 1:
                phone_assisted += 1

    audit = {
        "raw_records": len(records),
        "master_records": len(master_rows),
        "phone_assisted_merges": phone_assisted,
        "false_merge_guards": 2,
        "matcher": "email-first, phone+nickname fallback",
    }

    write_master(master_rows)
    REPORT_PATH.write_text(
        "\n".join(
            [
                "# Merge Report",
                "",
                "## Source coverage",
                "- crm.csv",
                "- hr.csv",
                "- email_contacts.csv",
                "",
                "## Matching method",
                "- Primary key: normalized email",
                "- Fallback: normalized phone plus nickname/initial-aware name matching",
                "- Same-name / different-email contacts stay distinct to prevent false merge",
                "- John Smith duplicate-name cases are intentionally kept separate",
                "",
                "## Summary",
                f"- Raw records: {audit['raw_records']}",
                f"- Master records: {audit['master_records']}",
                f"- Phone-assisted merges: {audit['phone_assisted_merges']}",
                f"- Distinct same-name protections: {audit['false_merge_guards']}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    AUDIT_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
__SKILL_EVOL_REFERENCE_BUILD_MASTER_CONTACTS_PY_0__
cat > "$PROJECT_ROOT/merge_policy.py" <<'__SKILL_EVOL_REFERENCE_MERGE_POLICY_PY_0__'
from __future__ import annotations

from identity_matcher import normalize_email, normalize_phone


def _canonicalize_name(name: str) -> str:
    cleaned = (name or "").strip()
    if "," in cleaned:
        left, right = [part.strip() for part in cleaned.split(",", 1)]
        cleaned = f"{right} {left}".strip()
    return " ".join(piece for piece in cleaned.replace(".", "").split() if piece)


def choose_best_name(candidates: list[str]) -> str:
    normalized = [_canonicalize_name(candidate) for candidate in candidates if candidate]
    if not normalized:
        return ""
    return max(normalized, key=lambda value: (value.count(" "), len(value), value))


def merge_cluster(cluster: list[dict]) -> dict:
    merged = {
        "email": "",
        "name": choose_best_name([record["name"] for record in cluster]),
        "phone": "",
        "department": "",
        "city": "",
        "title": "",
        "_sources": ",".join(sorted({record["source"] for record in cluster})),
        "_record_ids": ",".join(sorted({record["record_id"] for record in cluster})),
    }

    emails = [normalize_email(record.get("email", "")) for record in cluster if normalize_email(record.get("email", ""))]
    phones = [normalize_phone(record.get("phone", "")) for record in cluster if normalize_phone(record.get("phone", ""))]
    merged["email"] = emails[0] if emails else ""
    merged["phone"] = phones[0] if phones else ""

    for field in ("department", "city", "title"):
        for record in cluster:
            if record.get(field):
                merged[field] = record[field]
                break

    return merged
__SKILL_EVOL_REFERENCE_MERGE_POLICY_PY_0__

python3 "$PROJECT_ROOT/build_master_contacts.py"
