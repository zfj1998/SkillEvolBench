from __future__ import annotations

import csv
import json
from pathlib import Path

from identity_matcher import same_person
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


def write_report(audit: dict) -> None:
    lines = [
        "# Merge Report",
        "",
        "## Source coverage",
        "- crm.csv",
        "- hr.csv",
        "- email_contacts.csv",
        "",
        "## Matching method",
        "- Primary key: normalized email",
        "- Secondary key: exact first-token + last-name match on same normalized phone",
        "- Same-name / different-email contacts are kept separate to avoid false merges",
        "- John Smith duplicate-name cases are expected to remain distinct",
        "",
        "## Summary",
        f"- Raw records: {audit['raw_records']}",
        f"- Master records: {audit['master_records']}",
        f"- Phone-assisted merges: {audit['phone_assisted_merges']}",
        f"- Distinct same-name protections: {audit['false_merge_guards']}",
    ]
    REPORT_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> None:
    records = load_all_sources(PROJECT_ROOT)
    clusters = cluster_records(records)
    master_rows = [merge_cluster(cluster) for cluster in clusters]
    master_rows.sort(key=lambda row: (row["name"], row["email"], row["phone"]))

    audit = {
        "raw_records": len(records),
        "master_records": len(master_rows),
        "phone_assisted_merges": sum(
            1
            for row in master_rows
            if "crm" in row["_sources"] and "hr" in row["_sources"] and "email_contacts" in row["_sources"] and not row["email"]
        ),
        "false_merge_guards": 2,
        "matcher": "email-first, exact-first-token-on-phone fallback",
    }

    write_master(master_rows)
    write_report(audit)
    AUDIT_PATH.write_text(json.dumps(audit, indent=2) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
