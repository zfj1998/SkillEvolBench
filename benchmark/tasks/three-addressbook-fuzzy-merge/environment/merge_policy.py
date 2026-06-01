from __future__ import annotations

from identity_matcher import normalize_email, normalize_phone


def choose_best_name(candidates: list[str]) -> str:
    names = [candidate for candidate in candidates if candidate]
    if not names:
        return ""
    return max(names, key=lambda value: (len(value), value.count(" "), value))


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
