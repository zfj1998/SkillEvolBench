from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    normalizer = read_text(PROJECT_ROOT / "category_normalizer.py")
    guard = read_text(PROJECT_ROOT / "rowcount_guard.py")
    script = read_text(PROJECT_ROOT / "query_electronics_report.py")

    public = run_checks(
        "public",
        [
            ("has_normalizer_module", lambda: "normalize_category" in normalizer or (_ for _ in ()).throw(AssertionError("normalize_category missing"))),
        ],
    )
    hidden = run_checks(
        "hidden",
        [
            ("normalizer_strips_zero_width", lambda: "\\u200b" in normalizer and "\\ufeff" in normalizer or (_ for _ in ()).throw(AssertionError("zero-width cleanup missing"))),
            ("rowcount_guard_uses_realistic_band", lambda: "EXPECTED_MIN = 850" in guard and "EXPECTED_MAX = 1050" in guard or (_ for _ in ()).throw(AssertionError("rowcount guard too weak"))),
            ("script_filters_with_normalizer", lambda: "normalize_category(row[\"category\"])" in script or (_ for _ in ()).throw(AssertionError("script still relies on narrow SQL category filter"))),
        ],
    )
    return emit_report("E3-LS5-T1", public, hidden)


if __name__ == "__main__":
    print_report(run())
