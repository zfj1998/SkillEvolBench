from __future__ import annotations

import csv
from pathlib import Path


def _read_csv(path: Path):
    with path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def load_all_sources(base_dir: Path) -> list[dict]:
    records: list[dict] = []

    for row in _read_csv(base_dir / "crm.csv"):
        records.append(
            {
                "source": "crm",
                "record_id": row["contact_id"],
                "name": row["display_name"].strip(),
                "email": row["email"].strip(),
                "phone": row["phone"].strip(),
                "department": row["department"].strip(),
                "city": row["city"].strip(),
                "title": "",
            }
        )

    for row in _read_csv(base_dir / "hr.csv"):
        records.append(
            {
                "source": "hr",
                "record_id": row["emp_id"],
                "name": row["full_name"].strip(),
                "email": row["work_email"].strip(),
                "phone": row["mobile"].strip(),
                "department": row["dept"].strip(),
                "city": "",
                "title": row["job_title"].strip(),
            }
        )

    for row in _read_csv(base_dir / "email_contacts.csv"):
        records.append(
            {
                "source": "email_contacts",
                "record_id": row["person_id"],
                "name": row["name"].strip(),
                "email": row["email_address"].strip(),
                "phone": row["phone_number"].strip(),
                "department": row["team"].strip(),
                "city": "",
                "title": "",
            }
        )

    return records
