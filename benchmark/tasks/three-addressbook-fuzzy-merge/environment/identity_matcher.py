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


def _canonical_first_token(name: str) -> str:
    cleaned = (name or "").strip().lower().replace(",", " ")
    tokens = [token for token in cleaned.split() if token]
    if not tokens:
        return ""
    token = tokens[0].strip(".")
    return NICKNAME_MAP.get(token, token)


def _last_token(name: str) -> str:
    cleaned = (name or "").strip().lower().replace(",", " ")
    tokens = [token.strip(".") for token in cleaned.split() if token]
    return tokens[-1] if tokens else ""


def same_person(left: dict, right: dict) -> bool:
    left_email = normalize_email(left.get("email", ""))
    right_email = normalize_email(right.get("email", ""))
    if left_email and right_email and left_email == right_email:
        return True

    left_phone = normalize_phone(left.get("phone", ""))
    right_phone = normalize_phone(right.get("phone", ""))
    if left_phone and right_phone and left_phone == right_phone:
        # Legacy behavior: when email is missing, require the same exact canonical first token.
        # This is too strict for Bob/Robert or O./Owen variants.
        return (
            _canonical_first_token(left.get("name", "")) == _canonical_first_token(right.get("name", ""))
            and _last_token(left.get("name", "")) == _last_token(right.get("name", ""))
        )

    return False
