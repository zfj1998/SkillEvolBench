import os
import random
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

random.seed(1337)

DB_NAME = "revenue.db"
TWOPLACES = Decimal("0.01")


def q2(x: Decimal) -> Decimal:
    return x.quantize(TWOPLACES, rounding=ROUND_HALF_UP)


def fmt_amount_variant(d: Decimal):
    """Return either REAL-like float or messy TEXT."""
    variants = [
        lambda v: float(v),
        lambda v: f"{v}",
        lambda v: f" {v} ",
        lambda v: f"{v:,.2f}",
    ]
    return random.choice(variants)(d)


def canonical_alias(canon):
    if canon == "Software":
        return random.choice([
            "Software", "software", " SOFTWARE ", "sw", "SW", "soft ware",
            "\ufeffSoftware", "Soft\u200bware", " software "
        ])
    if canon == "Hardware":
        return random.choice([
            "Hardware", "hardware", " hw ", "HW", "hard ware",
            "Hard\u200cware", "\ufeffhardware"
        ])
    if canon == "Services":
        return random.choice([
            "Services", "services", "service", "svc", " SVC ",
            "Ser\u200bdvices", "\ufeffservices"
        ])
    if canon == "Consulting":
        return random.choice([
            "Consulting", "consulting", "consult", "advisory",
            " CONSULTING ", "Con\u200dsulting", "\ufeffadvisory"
        ])
    raise ValueError(canon)


def invalid_amount_token():
    return random.choice([None, "", " ", "NA", "N/A", "null", "None", "bad"])


def maybe_invalid_amount(valid_decimal: Decimal, p_invalid=0.08):
    if random.random() < p_invalid:
        return invalid_amount_token()
    return fmt_amount_variant(valid_decimal)


def main():
    if os.path.exists(DB_NAME):
        os.remove(DB_NAME)

    conn = sqlite3.connect(DB_NAME)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            total_amount,
            order_date TEXT,
            status TEXT,
            is_test INTEGER
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY,
            order_id INTEGER,
            product_line TEXT,
            item_amount,
            source_note TEXT
        )
        """
    )

    order_id = 1
    item_id = 1

    valid_order_ids = []
    valid_order_total_sum = Decimal("0.00")
    included_item_sum = Decimal("0.00")

    statuses = ["POSTED", "PENDING", "CANCELLED"]

    # Core dataset
    for _ in range(1800):
        customer_id = random.randint(1, 400)
        order_date = f"2024-{random.randint(1,12):02d}-{random.randint(1,28):02d}"

        status = random.choices(statuses, weights=[0.72, 0.18, 0.10])[0]
        is_test = 1 if random.random() < 0.07 else 0
        is_valid_order = status == "POSTED" and is_test == 0

        n_items = random.randint(1, 4)
        canonical_lines = ["Software", "Hardware", "Services", "Consulting"]

        item_rows = []
        valid_item_amounts_for_order = []
        included_item_amounts_for_order = []

        for _j in range(n_items):
            canon = random.choice(canonical_lines)
            amt = q2(Decimal(str(random.uniform(50, 5000))))
            raw_product_line = canonical_alias(canon)

            # Sometimes make product line unrecognized/blank
            if random.random() < 0.09:
                raw_product_line = random.choice([
                    "", " ", "\u200b", "Unknown", "Misc", "N/A", "other", "soft-ware"
                ])

            raw_item_amount = maybe_invalid_amount(amt, p_invalid=0.10)
            item_rows.append((item_id, order_id, raw_product_line, raw_item_amount, "generated"))

            # Track "true" included item sum according to business rules
            if raw_item_amount not in (None, "", " ", "NA", "N/A", "null", "None", "bad"):
                normalized = str(raw_product_line)
                for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
                    normalized = normalized.replace(ch, "")
                normalized = " ".join(normalized.strip().split()).lower()
                mapping = {
                    "software": "Software",
                    "sw": "Software",
                    "soft ware": "Software",
                    "hardware": "Hardware",
                    "hw": "Hardware",
                    "hard ware": "Hardware",
                    "services": "Services",
                    "service": "Services",
                    "svc": "Services",
                    "consulting": "Consulting",
                    "consult": "Consulting",
                    "advisory": "Consulting",
                }
                if normalized in mapping:
                    included_item_amounts_for_order.append(amt)
                valid_item_amounts_for_order.append(amt)

            item_id += 1

        # Usually order total equals all parseable item amounts, but sometimes not.
        if random.random() < 0.12:
            adjustment = q2(Decimal(str(random.uniform(-15, 15))))
            order_total = q2(sum(valid_item_amounts_for_order, Decimal("0.00")) + adjustment)
        else:
            order_total = q2(sum(valid_item_amounts_for_order, Decimal("0.00")))

        raw_order_total = maybe_invalid_amount(order_total, p_invalid=0.06)

        cur.execute(
            "INSERT INTO orders (id, customer_id, total_amount, order_date, status, is_test) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, customer_id, raw_order_total, order_date, status, is_test),
        )

        cur.executemany(
            "INSERT INTO order_items (id, order_id, product_line, item_amount, source_note) VALUES (?, ?, ?, ?, ?)",
            item_rows,
        )

        if is_valid_order:
            valid_order_ids.append(order_id)
            if raw_order_total not in (None, "", " ", "NA", "N/A", "null", "None", "bad"):
                valid_order_total_sum += order_total
            included_item_sum += sum(included_item_amounts_for_order, Decimal("0.00"))

        order_id += 1

    # Add orphan items
    for _ in range(120):
        fake_order_id = random.randint(order_id + 1000, order_id + 5000)
        canon = random.choice(["Software", "Hardware", "Services", "Consulting"])
        amt = q2(Decimal(str(random.uniform(25, 2500))))
        raw_product_line = canonical_alias(canon)
        raw_item_amount = maybe_invalid_amount(amt, p_invalid=0.12)
        cur.execute(
            "INSERT INTO order_items (id, order_id, product_line, item_amount, source_note) VALUES (?, ?, ?, ?, ?)",
            (item_id, fake_order_id, raw_product_line, raw_item_amount, "orphan"),
        )
        item_id += 1

    # Add a few targeted edge cases
    targeted_orders = [
        # valid order, recognized aliases, comma-formatted total
        ("POSTED", 0, "1,234.56", [
            (" sw ", "200.00"),
            ("\ufeffhardware", "300.00"),
            ("svc", "400.00"),
            ("advisory", "334.56"),
        ]),
        # valid order, blank/unrecognized product lines causing mismatch
        ("POSTED", 0, "900.00", [
            ("Unknown", "300.00"),
            ("\u200b", "200.00"),
            ("software", "400.00"),
        ]),
        # filtered-out order, should not count
        ("CANCELLED", 0, "777.77", [
            ("software", "777.77"),
        ]),
        # valid order with invalid total but valid items
        ("POSTED", 0, "bad", [
            ("consult", "100.00"),
            ("service", "200.00"),
        ]),
    ]

    for status, is_test, total_amount, items in targeted_orders:
        cur.execute(
            "INSERT INTO orders (id, customer_id, total_amount, order_date, status, is_test) VALUES (?, ?, ?, ?, ?, ?)",
            (order_id, random.randint(1, 400), total_amount, "2024-12-15", status, is_test),
        )
        for pl, amt in items:
            cur.execute(
                "INSERT INTO order_items (id, order_id, product_line, item_amount, source_note) VALUES (?, ?, ?, ?, ?)",
                (item_id, order_id, pl, amt, "targeted"),
            )
            item_id += 1
        order_id += 1

    conn.commit()
    conn.close()
    print("Generated revenue.db with messy revenue audit cases.")


if __name__ == "__main__":
    main()