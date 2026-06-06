import os
import random
import sqlite3
from datetime import date, timedelta

random.seed(1337)

DB_PATH = "store.db"


def ensure_project_dir():
    os.makedirs(".", exist_ok=True)


def remove_zero_width(s: str) -> str:
    for ch in ("\u200b", "\u200c", "\u200d", "\ufeff"):
        s = s.replace(ch, "")
    return s


def normalize_email(email):
    if email is None:
        return None
    s = str(email).strip().lower()
    s = remove_zero_width(s)
    if s in ("", "null", "none", "na"):
        return None
    return s


def random_signup():
    start = date(2020, 1, 1)
    return (start + timedelta(days=random.randint(0, 1600))).isoformat()


def random_order_date_valid():
    d = date(2023, 1, 1) + timedelta(days=random.randint(0, 730))
    fmt = random.choice(["iso", "slash", "us"])
    if fmt == "iso":
        return d.strftime("%Y-%m-%d")
    if fmt == "slash":
        return d.strftime("%Y/%m/%d")
    return d.strftime("%m/%d/%Y")


def random_order_date_invalid():
    return random.choice(
        [
            "2024-13-01",
            "2024/99/99",
            "31/31/2024",
            "not-a-date",
            "",
            "2024-02-30",
        ]
    )


def amount_to_storage(value):
    style = random.choice(
        ["float", "plain", "ws", "currency", "comma", "currency_ws"]
    )
    if style == "float":
        return round(value, 2)
    if style == "plain":
        return f"{value:.2f}"
    if style == "ws":
        return f"  {value:.2f}  "
    if style == "currency":
        return f"${value:.2f}"
    if style == "comma":
        return f"{value:,.2f}"
    return f"  ${value:,.2f}  "


def bad_amount():
    return random.choice(
        ["", "abc", "null", "None", "$", "1,2,3", "12.3.4", "  ", None]
    )


def status_variant(base):
    variants = {
        "paid": ["paid", "PAID", " paid ", "Paid"],
        "shipped": ["shipped", "SHIPPED", " shipped ", "Shipped"],
        "bad": ["pending", "cancelled", "refunded", " failed ", "", "unknown"],
    }
    return random.choice(variants[base])


def source_variant():
    return random.choice(["web", "mobile", "store", "import", "partner"])


def main():
    ensure_project_dir()
    if os.path.exists(DB_PATH):
        os.remove(DB_PATH)

    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE customers (
            id INTEGER PRIMARY KEY,
            name TEXT,
            email TEXT,
            city TEXT,
            signup_date TEXT
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY,
            customer_id INTEGER,
            amount,
            order_date TEXT,
            status TEXT,
            source TEXT
        )
        """
    )

    customer_rows = []
    logical_customers = []

    cities = ["New York", "Chicago", "Dallas", "Seattle", "Austin", "Miami"]

    # 900 unique-email logical customers
    next_customer_id = 1
    for i in range(1, 901):
        email = f"customer{i:04d}@example.com"
        row = (
            next_customer_id,
            f"Customer_{i:04d}",
            email,
            random.choice(cities),
            random_signup(),
        )
        customer_rows.append(row)
        logical_customers.append(
            {
                "canonical_id": next_customer_id,
                "all_ids": [next_customer_id],
                "name": row[1],
                "norm_email": normalize_email(email),
            }
        )
        next_customer_id += 1

    # 50 duplicate groups, each with 2 rows => 50 logical customers, 100 physical rows
    for i in range(901, 951):
        base_email = f"dup{i:04d}@example.com"
        email1 = base_email.upper()
        email2 = " \u200b" + base_email + " "
        id1 = next_customer_id
        customer_rows.append(
            (
                id1,
                f"Customer_{i:04d}_A",
                email1,
                random.choice(cities),
                random_signup(),
            )
        )
        next_customer_id += 1
        id2 = next_customer_id
        customer_rows.append(
            (
                id2,
                f"Customer_{i:04d}_B",
                email2,
                random.choice(cities),
                random_signup(),
            )
        )
        next_customer_id += 1
        logical_customers.append(
            {
                "canonical_id": min(id1, id2),
                "all_ids": [id1, id2],
                "name": f"Customer_{i:04d}_A",
                "norm_email": normalize_email(base_email),
            }
        )

    # 50 missing-email customers, each remains distinct logical customer
    missing_email_values = [None, "", " ", "NULL", "None", "na", "\u200b", " NA "]
    for i in range(951, 1001):
        email = random.choice(missing_email_values)
        row = (
            next_customer_id,
            f"Customer_{i:04d}",
            email,
            random.choice(cities),
            random_signup(),
        )
        customer_rows.append(row)
        logical_customers.append(
            {
                "canonical_id": next_customer_id,
                "all_ids": [next_customer_id],
                "name": row[1],
                "norm_email": None,
            }
        )
        next_customer_id += 1

    cur.executemany(
        "INSERT INTO customers (id, name, email, city, signup_date) VALUES (?, ?, ?, ?, ?)",
        customer_rows,
    )

    # Orders
    order_rows = []
    next_order_id = 1

    # 700 logical customers active, 300 inactive
    active_indices = set(random.sample(range(len(logical_customers)), 700))

    for idx, logical in enumerate(logical_customers):
        ids = logical["all_ids"]
        if idx in active_indices:
            # 1-6 qualifying orders, spread across duplicate ids if any
            qcount = random.randint(1, 6)
            for _ in range(qcount):
                cust_id = random.choice(ids)
                amount = round(random.uniform(5, 2500), 2)
                order_rows.append(
                    (
                        next_order_id,
                        cust_id,
                        amount_to_storage(amount),
                        random_order_date_valid(),
                        status_variant(random.choice(["paid", "shipped"])),
                        source_variant(),
                    )
                )
                next_order_id += 1

            # plus 0-3 junk orders for same logical customer
            for _ in range(random.randint(0, 3)):
                cust_id = random.choice(ids)
                junk_kind = random.choice(["bad_status", "bad_amount", "bad_date", "nonpos"])
                if junk_kind == "bad_status":
                    amount = round(random.uniform(5, 500), 2)
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount_to_storage(amount),
                            random_order_date_valid(),
                            status_variant("bad"),
                            source_variant(),
                        )
                    )
                elif junk_kind == "bad_amount":
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            bad_amount(),
                            random_order_date_valid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                elif junk_kind == "bad_date":
                    amount = round(random.uniform(5, 500), 2)
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount_to_storage(amount),
                            random_order_date_invalid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                else:
                    amount = random.choice([0, "0", "0.00", -5, "-10.00", "$0.00"])
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount,
                            random_order_date_valid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                next_order_id += 1
        else:
            # inactive logical customers may still have only non-qualifying orders
            for _ in range(random.randint(0, 2)):
                cust_id = random.choice(ids)
                junk_kind = random.choice(["bad_status", "bad_amount", "bad_date", "nonpos"])
                if junk_kind == "bad_status":
                    amount = round(random.uniform(5, 500), 2)
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount_to_storage(amount),
                            random_order_date_valid(),
                            status_variant("bad"),
                            source_variant(),
                        )
                    )
                elif junk_kind == "bad_amount":
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            bad_amount(),
                            random_order_date_valid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                elif junk_kind == "bad_date":
                    amount = round(random.uniform(5, 500), 2)
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount_to_storage(amount),
                            random_order_date_invalid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                else:
                    amount = random.choice([0, "0", "0.00", -1, "-2.50", "$0.00"])
                    order_rows.append(
                        (
                            next_order_id,
                            cust_id,
                            amount,
                            random_order_date_valid(),
                            status_variant(random.choice(["paid", "shipped"])),
                            source_variant(),
                        )
                    )
                next_order_id += 1

    # Add orphan orders with nonexistent customer ids
    for _ in range(120):
        fake_customer_id = random.randint(5000, 7000)
        amount = round(random.uniform(10, 900), 2)
        order_rows.append(
            (
                next_order_id,
                fake_customer_id,
                amount_to_storage(amount),
                random_order_date_valid(),
                status_variant(random.choice(["paid", "shipped"])),
                source_variant(),
            )
        )
        next_order_id += 1

    cur.executemany(
        """
        INSERT INTO orders (id, customer_id, amount, order_date, status, source)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        order_rows,
    )

    conn.commit()
    conn.close()

    print(
        f"Generated {len(customer_rows)} customer rows, "
        f"{len(logical_customers)} logical customers, "
        f"{len(order_rows)} orders."
    )


if __name__ == "__main__":
    main()