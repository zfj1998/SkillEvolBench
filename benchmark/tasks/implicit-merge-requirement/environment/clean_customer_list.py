from __future__ import annotations

import csv
from pathlib import Path

from customer_merge_policy import merge_customer
from merge_audit import write_audit
from source_discovery import discover_sources


PROJECT_ROOT = Path(__file__).resolve().parent


def normalize_email(value: str) -> str:
    return (value or "").strip().lower()


def _to_record(source_name: str, row: dict) -> dict:
    if source_name == "crm_export.csv":
        return {
            "source": "crm_export",
            "email": normalize_email(row.get("email", "")),
            "name": f"{row.get('first_name', '').strip()} {row.get('last_name', '').strip()}".strip(),
            "phone": row.get("phone", "").strip(),
            "city": row.get("city", "").strip(),
            "company": row.get("company", "").strip(),
            "tag": row.get("tag", "").strip(),
        }
    if source_name == "newsletter_list.csv":
        return {
            "source": "newsletter_list",
            "email": normalize_email(row.get("email", "")),
            "name": row.get("full_name", "").strip(),
            "phone": "",
            "city": row.get("city", "").strip(),
            "company": "",
            "tag": "newsletter",
        }
    return {
        "source": "event_attendees",
        "email": normalize_email(row.get("email_address", "")),
        "name": row.get("name", "").strip(),
        "phone": row.get("phone", "").strip(),
        "city": "",
        "company": row.get("company", "").strip(),
        "tag": row.get("event", "").strip(),
    }


def main() -> None:
    discovered = discover_sources(PROJECT_ROOT)
    merged: dict[str, dict] = {}
    raw_count = 0

    for path in discovered:
        with path.open(newline="", encoding="utf-8") as handle:
            rows = list(csv.DictReader(handle))
        raw_count += len(rows)
        for row in rows:
            record = _to_record(path.name, row)
            if not record["email"]:
                continue
            merged[record["email"]] = merge_customer(merged.get(record["email"]), record)

    output_rows = []
    for email, record in sorted(merged.items()):
        output_rows.append(
            {
                "email": email,
                "name": record.get("name", ""),
                "phone": record.get("phone", ""),
                "city": record.get("city", ""),
                "company": record.get("company", ""),
                "tag": record.get("tag", ""),
                "_sources": ",".join(record["_sources"]),
            }
        )

    with (PROJECT_ROOT / "customer_list.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["email", "name", "phone", "city", "company", "tag", "_sources"])
        writer.writeheader()
        writer.writerows(output_rows)

    write_audit(PROJECT_ROOT / "customer_merge_audit.json", raw_count, len(output_rows), [path.name for path in discovered])


if __name__ == "__main__":
    main()
