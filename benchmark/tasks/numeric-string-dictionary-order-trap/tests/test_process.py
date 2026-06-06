from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
NORMALIZER = PROJECT / "id_normalizer.py"
SORTER = PROJECT / "catalog_sort.py"


def run():
    normalizer = read_text(NORMALIZER)
    sorter = read_text(SORTER)
    public = run_checks("public", [
        ("normalizer_present", lambda: "normalize_product_id" in normalizer or (_ for _ in ()).throw(AssertionError("id normalizer missing"))),
    ])
    hidden = run_checks("hidden", [
        ("int_conversion_present", lambda: "int(" in normalizer or (_ for _ in ()).throw(AssertionError("numeric normalization missing"))),
        ("no_raw_string_sort", lambda: "product_id_normalized" in sorter or (_ for _ in ()).throw(AssertionError("sort not using normalized ids"))),
        ("no_plain_lexicographic_key", lambda: "\"product_id\"" not in sorter or "product_id_normalized" in sorter or (_ for _ in ()).throw(AssertionError("raw product_id sort detected"))),
    ])
    return emit_report("E3-LS2-T5", public, hidden)


if __name__ == "__main__":
    print_report(run())
