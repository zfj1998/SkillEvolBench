from __future__ import annotations

import re

from duplicate_guard import username_is_duplicate

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def screen_candidate(record, username_snapshot):
    errors = []
    if "name" not in record:
        errors.append({"field": "name", "reason": "missing"})
    elif record["name"] == "":
        errors.append({"field": "name", "reason": "empty"})

    if "email" not in record:
        errors.append({"field": "email", "reason": "missing"})
    elif not EMAIL_RE.match(record["email"]):
        errors.append({"field": "email", "reason": "format"})

    if "username" in record and username_is_duplicate(record["username"], username_snapshot):
        errors.append({"field": "username", "reason": "duplicate"})

    return errors
