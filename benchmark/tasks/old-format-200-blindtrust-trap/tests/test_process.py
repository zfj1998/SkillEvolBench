from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"


def run():
    fetch = read_text(PROJECT / "fetch_users.py")
    projection = read_text(PROJECT / "compat_projection.py")
    public = run_checks("public", [
        ("reads_api_docs", lambda: "api_docs.md" in fetch or (_ for _ in ()).throw(AssertionError("api_docs.md is not read"))),
    ])
    hidden = run_checks("hidden", [
        ("uses_canonical_fields", lambda: all(field in projection for field in ("username", "phone", "email", "created_at")) or (_ for _ in ()).throw(AssertionError("canonical fields not projected"))),
        ("does_not_prefer_deprecated", lambda: "prefer_deprecated and" not in projection or (_ for _ in ()).throw(AssertionError("deprecated fields still preferred"))),
    ])
    return emit_report("E2-LS5-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
