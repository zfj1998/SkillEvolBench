from __future__ import annotations

from pathlib import Path

import sys

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"

if str(PROJECT) not in sys.path:
    sys.path.insert(0, str(PROJECT))

from compat_projection import project_user
from verifier_lib.runtime import emit_report, print_report, run_checks


def run():
    contract = {
        "deprecated": {
            "username": "user_name",
            "phone": "phone_number",
            "email": "email_address",
            "created_at": "created_date",
        },
        "compat_mode": "dual-read",
    }
    raw = {
        "id": 1,
        "username": "canonical",
        "user_name": "deprecated",
        "phone": "new-phone",
        "phone_number": "old-phone",
        "email": "new@example.com",
        "email_address": "old@example.com",
        "created_at": "2026-01-02",
        "created_date": "2025-01-02",
    }
    projected = project_user(raw, contract)
    public = run_checks("public", [
        ("reads_api_docs", lambda: (PROJECT / "api_docs.md").is_file() or (_ for _ in ()).throw(AssertionError("api_docs.md is missing"))),
    ])
    hidden = run_checks("hidden", [
        ("uses_canonical_fields", lambda: all(field in projected for field in ("username", "phone", "email", "created_at")) or (_ for _ in ()).throw(AssertionError("canonical fields not projected"))),
        ("does_not_prefer_deprecated", lambda: projected["username"] == "canonical" and projected["phone"] == "new-phone" and projected["email"] == "new@example.com" and projected["created_at"] == "2026-01-02" or (_ for _ in ()).throw(AssertionError(f"deprecated fields preferred: {projected!r}"))),
    ])
    return emit_report("E2-LS5-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
