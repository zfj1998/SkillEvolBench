import os
import random
import sqlite3
from decimal import Decimal, ROUND_HALF_UP

random.seed(1337)

DB_PATH = "products.db"


def ensure_project_dir():
    os.makedirs(".", exist_ok=True)


def normalize_category_for_generation(base):
    return base


def category_variant(base):
    if base != "Electronics":
        variants = [
            base,
            base.lower(),
            f" {base} ",
            f"\ufeff{base}",
            f"{base}\u200b",
        ]
        return random.choice(variants)

    variants = [
        "Electronics",
        " electronics ",
        "ELECTRONICS",
        "\ufeffElectronics",
        "Electronics\u200b",
        "Electronics\u200c",
        " Electronics ",
    ]
    return random.choice(variants)


def maybe_dirty_price(value):
    s = f"{value:.2f}"
    options = [
        s,
        f" {s} ",
        f"${s}",
    ]
    if value >= 1000:
        options.append(f"{value:,.2f}")
        options.append(f"${value:,.2f}")
    return random.choice(options)


def maybe_dirty_stock(value):
    options = [
        str(value),
        f" {value} ",
    ]
    if random.random() < 0.2:
        options.append(f"{value}.0")
    return random.choice(options)


def invalid_price():
    return random.choice([
        "",
        " ",
        "N/A",
        "NA",
        "NULL",
        "None",
        "-5",
        "nan",
        "inf",
        "-inf",
    ])


def invalid_stock():
    return random.choice([
        "",
        " ",
        "N/A",
        "NA",
        "NULL",
        "None",
        "-1",
        "3.5",
        "nan",
    ])


def main():
    ensure_project_dir()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE products(
            id INTEGER,
            name TEXT,
            category TEXT,
            price TEXT,
            stock_quantity TEXT,
            supplier TEXT,
            active INTEGER,
            created_at TEXT
        )
        """
    )

    categories = ["Electronics", "Clothing", "Books", "Home & Garden", "Sports"]
    suppliers = ["SupplierA", "SupplierB", "SupplierC", "SupplierD"]

    rows = []
    row_id = 1

    # 1000 canonical electronics rows, but some are invalid/inactive and some non-canonical
    # variants should still count after normalization.
    valid_electronics_count = 0

    for i in range(1000):
        category = category_variant("Electronics")
        active = 1
        price_num = round(random.uniform(25, 1800), 2)
        stock_num = random.randint(0, 250)

        price = maybe_dirty_price(price_num)
        stock = maybe_dirty_stock(stock_num)

        # Inject a controlled number of invalid/inactive electronics rows.
        if i < 35:
            price = invalid_price()
        elif 35 <= i < 60:
            stock = invalid_stock()
        elif 60 <= i < 85:
            active = 0
        else:
            valid_electronics_count += 1

        rows.append(
            (
                row_id,
                f"Electronics_Item_{row_id:04d}",
                category,
                price,
                stock,
                random.choice(suppliers),
                active,
                f"2024-01-{(i % 28) + 1:02d}",
            )
        )
        row_id += 1

    # Other categories, including some deceptive near-matches that should NOT count.
    deceptive_categories = [
        "Electronic",
        "Electronics & Gadgets",
        "Home Electronics",
        "Consumer Electronics",
    ]

    for base in categories[1:]:
        for i in range(1000):
            category = category_variant(base)
            price_num = round(random.uniform(10, 900), 2)
            stock_num = random.randint(0, 220)
            rows.append(
                (
                    row_id,
                    f"{base}_Item_{row_id:04d}",
                    category,
                    maybe_dirty_price(price_num),
                    maybe_dirty_stock(stock_num),
                    random.choice(suppliers),
                    1,
                    f"2024-02-{(i % 28) + 1:02d}",
                )
            )
            row_id += 1

    # Add deceptive rows that look electronics-related but must not count.
    for i in range(120):
        base = random.choice(deceptive_categories)
        price_num = round(random.uniform(50, 1500), 2)
        stock_num = random.randint(0, 180)
        rows.append(
            (
                row_id,
                f"Trap_Item_{row_id:04d}",
                random.choice([
                    base,
                    f" {base} ",
                    f"\ufeff{base}",
                    f"{base}\u200b",
                    base.upper(),
                ]),
                maybe_dirty_price(price_num),
                maybe_dirty_stock(stock_num),
                random.choice(suppliers),
                1,
                "2024-03-15",
            )
        )
        row_id += 1

    random.shuffle(rows)
    cur.executemany(
        """
        INSERT INTO products(
            id, name, category, price, stock_quantity, supplier, active, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        rows,
    )
    conn.commit()
    conn.close()

    print(f"Generated {len(rows)} rows in {DB_PATH}")
    print(f"Expected valid Electronics rows after cleaning: {valid_electronics_count}")


if __name__ == "__main__":
    main()