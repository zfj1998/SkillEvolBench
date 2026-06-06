from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

TASK_ROOT = Path(__file__).resolve().parents[1]
PROJECT = TASK_ROOT / "project"
SCRIPT = PROJECT / "process_transaction_log.py"
DATE_NORM = PROJECT / "date_normalizer.py"
PRODUCT_ORDER = PROJECT / "product_ordering.py"
DEDUP = PROJECT / "dedup_policy.py"


def run():
    script = read_text(SCRIPT)
    date_norm = read_text(DATE_NORM)
    product_order = read_text(PRODUCT_ORDER)
    dedup = read_text(DEDUP)
    public = run_checks("public", [
        ("date_parsing_present", lambda: "to_datetime" in date_norm or (_ for _ in ()).throw(AssertionError("date parsing missing"))),
    ])
    hidden = run_checks("hidden", [
        ("natural_product_sort_present", lambda: "int(" in product_order or (_ for _ in ()).throw(AssertionError("natural product ordering missing"))),
        ("semantic_dedup_present", lambda: all(token in dedup for token in ["date", "product_id", "customer_id", "amount", "quantity", "channel"]) or (_ for _ in ()).throw(AssertionError("semantic dedup key missing"))),
        ("sort_uses_normalized_fields", lambda: "parsed_date" in script and "product_sort_key" in script or (_ for _ in ()).throw(AssertionError("normalized sort fields missing"))),
    ])
    return emit_report("E3-LS2-T6", public, hidden)


if __name__ == "__main__":
    print_report(run())
