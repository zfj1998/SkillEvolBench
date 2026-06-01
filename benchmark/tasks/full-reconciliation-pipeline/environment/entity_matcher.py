from __future__ import annotations

import re


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


def same_entity(left: dict, right: dict) -> bool:
    left_email = normalize_email(left.get("email", ""))
    right_email = normalize_email(right.get("email", ""))
    return bool(left_email and right_email and left_email == right_email)
