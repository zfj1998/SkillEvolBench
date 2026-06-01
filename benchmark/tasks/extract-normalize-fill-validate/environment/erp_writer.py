from __future__ import annotations

import csv


def write_rows(data: dict, out_path) -> None:
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        # BUG: header order still follows extraction order instead of ERP contract.
        writer.writerow(["invoice_id", "customer", "invoice_date", "amount", "item_description"])
        for item in data["items"]:
            writer.writerow(
                [
                    data["invoice_id"],
                    data["customer"],
                    data["invoice_date"],
                    f"{item['amount']:.2f}",
                    item["item_description"],
                ]
            )
