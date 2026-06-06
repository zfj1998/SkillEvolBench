from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
ALIASES = PROJECT / "product_aliases.py"
CLEANER = PROJECT / "snapshot_cleaner.py"
SCRIPT = PROJECT / "compare_sales.py"


def run():
    aliases = read_text(ALIASES)
    cleaner = read_text(CLEANER)
    script = read_text(SCRIPT)
    public = run_checks("public", [
        ("has_alignment_step", lambda: "canonical_product" in cleaner or (_ for _ in ()).throw(AssertionError("canonical alignment step missing"))),
    ])
    hidden = run_checks("hidden", [
        ("uses_alias_or_normalization", lambda: "PRODUCT_ALIASES" in aliases and "re.sub" in cleaner or (_ for _ in ()).throw(AssertionError("product normalization too weak"))),
        ("compares_on_aligned_key", lambda: "on=\"canonical_product\"" in script or "on='canonical_product'" in script or (_ for _ in ()).throw(AssertionError("comparison not based on aligned key"))),
        ("avoids_raw_product_name_join", lambda: "on=\"product_name\"" not in script and "on='product_name'" not in script or (_ for _ in ()).throw(AssertionError("still joining on raw product_name"))),
        ("deduplicates_latest_snapshot", lambda: "snapshot_rank" in cleaner and "drop_duplicates" in cleaner or (_ for _ in ()).throw(AssertionError("snapshot dedup step missing"))),
    ])
    return emit_report("E3-LS3-T4", public, hidden)


if __name__ == "__main__":
    print_report(run())
