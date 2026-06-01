from __future__ import annotations

from pathlib import Path


def load_contract(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    return {
        "canonical_fields": ["id", "username", "phone", "email", "created_at"],
        "deprecated": {
            "username": "user_name",
            "phone": "phone_number",
            "email": "email_address",
            "created_at": "created_date",
        },
        "compat_mode": "dual-read" if "Compatibility note" in text else "strict",
    }
