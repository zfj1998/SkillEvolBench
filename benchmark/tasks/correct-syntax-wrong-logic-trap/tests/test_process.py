from __future__ import annotations

from pathlib import Path

from verifier_lib.runtime import emit_report, print_report, read_text, run_checks

PROJECT_ROOT = Path(__import__("os").environ.get("PROJECT_ROOT", "/root/task")).resolve()


def run():
    guard = read_text(PROJECT_ROOT / "activity_guard.py")
    validity = read_text(PROJECT_ROOT / "order_validity.py")

    hidden = run_checks(
        "hidden",
        [
            ("activity_guard_checks_order_presence", lambda: "order_id" in guard or (_ for _ in ()).throw(AssertionError("order presence guard missing"))),
            ("activity_guard_checks_status_amount_date", lambda: "valid_order_status" in guard and "parse_amount" in guard and "valid_order_date" in guard or (_ for _ in ()).throw(AssertionError("valid-order checks missing"))),
            ("validity_module_supports_business_filters", lambda: "paid" in validity and "shipped" in validity and "Decimal" in validity and "datetime.strptime" in validity or (_ for _ in ()).throw(AssertionError("order validity rules incomplete"))),
        ],
    )
    return emit_report("E3-LS5-T5", {"section": "public", "results": [], "passed": 0, "total": 0}, hidden)


if __name__ == "__main__":
    print_report(run())
