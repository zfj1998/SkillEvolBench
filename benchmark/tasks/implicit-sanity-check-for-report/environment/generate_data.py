import os
import random
import sqlite3
from decimal import Decimal, ROUND_HALF_UP
from datetime import date, timedelta

random.seed(1337)

DB_PATH = "daily_sales.db"


def money(x):
    return str(Decimal(x).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))


def daterange(start, end):
    cur = start
    while cur <= end:
        yield cur
        cur += timedelta(days=1)


def add_row(rows, row_id, dt, product, amount, quantity):
    rows.append((row_id, dt, product, amount, quantity))
    return row_id + 1


def main():
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE sales(
            id INTEGER PRIMARY KEY,
            date TEXT,
            product TEXT,
            amount TEXT,
            quantity TEXT
        )
        """
    )

    rows = []
    row_id = 1

    products = ["Widget_A", "Widget_B", "Gadget_C", "Gadget_D", "Tool_E"]

    # March 15 and 16 should still end up missing after cleaning.
    missing_days = {"2024-03-15", "2024-03-16"}

    start = date(2024, 3, 1)
    end = date(2024, 3, 31)

    for d in daterange(start, end):
        ds = d.isoformat()
        if ds in missing_days:
            # Add only invalid rows on these days so they remain missing.
            row_id = add_row(rows, row_id, ds, "Widget_A", "NA", "2")
            row_id = add_row(rows, row_id, " " + ds + " ", "Widget_B", "", "3")
            row_id = add_row(rows, row_id, ds.replace("-", "/"), "Tool_E", "$oops", "x")
            continue

        n = random.randint(10, 18)
        day_valid = []

        for _ in range(n):
            product = random.choice(products)
            amount_val = Decimal(random.randint(1200, 25000)) / Decimal(100)
            qty_val = random.randint(1, 8)

            # Canonical values
            canon_date = ds
            canon_product = product
            canon_amount = money(amount_val)
            canon_qty = str(qty_val)

            # Store with format variations that should still parse
            date_variant = random.choice([
                canon_date,
                " " + canon_date,
                canon_date + " ",
                canon_date.replace("-", "/"),
            ])
            amount_variant = random.choice([
                canon_amount,
                " " + canon_amount + " ",
                "$" + canon_amount,
            ])
            qty_variant = random.choice([
                canon_qty,
                " " + canon_qty + " ",
            ])
            product_variant = random.choice([
                canon_product,
                " " + canon_product,
                canon_product + " ",
            ])

            row_id = add_row(rows, row_id, date_variant, product_variant, amount_variant, qty_variant)
            day_valid.append((canon_date, canon_product.strip(), canon_amount, canon_qty))

            # Sometimes add a duplicate retry with different formatting but same normalized values.
            if random.random() < 0.28:
                dup_date = random.choice([
                    canon_date,
                    " " + canon_date + " ",
                    canon_date.replace("-", "/"),
                ])
                dup_amount = random.choice([
                    canon_amount,
                    "$" + canon_amount,
                    " " + canon_amount,
                ])
                dup_qty = random.choice([
                    canon_qty,
                    " " + canon_qty,
                ])
                dup_product = random.choice([
                    canon_product,
                    " " + canon_product,
                    canon_product + " ",
                ])
                row_id = add_row(rows, row_id, dup_date, dup_product, dup_amount, dup_qty)

        # Add malformed noise for every valid day.
        noise = [
            (ds, "Widget_A", "NA", "1"),
            (ds, "Widget_A", "null", "2"),
            (ds, "Widget_A", "None", "3"),
            (ds, "Widget_A", "", "4"),
            (ds, "Widget_A", "abc", "5"),
            (ds, "Widget_A", "$12.3.4", "6"),
            (ds, "Widget_A", "10.00", "x"),
            ("2024-04-01", "Widget_A", "99.99", "1"),
            ("2024-02-29", "Widget_A", "88.88", "1"),
            ("2024-03-32", "Widget_A", "77.77", "1"),
        ]
        for rec in noise:
            row_id = add_row(rows, row_id, *rec)

    # Global extra rows that should be ignored.
    extras = [
        (" 2024-04-15 ", "Widget_B", "$123.45", "2"),
        ("2024/02/28", "Gadget_C", "45.67", "1"),
        ("not-a-date", "Tool_E", "55.55", "1"),
        ("2024-03-10", "Widget_B", "N/A", "2"),
        ("2024-03-10", "Widget_B", "$100.00", " 2x "),
    ]
    for rec in extras:
        row_id = add_row(rows, row_id, *rec)

    cur.executemany(
        "INSERT INTO sales(id, date, product, amount, quantity) VALUES (?, ?, ?, ?, ?)",
        rows,
    )
    conn.commit()
    conn.close()

    print(f"Created {DB_PATH} with {len(rows)} rows")


if __name__ == "__main__":
    main()