import csv
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path
from datetime import date, timedelta

ZERO_WIDTHS = ["\u200b", "\u200c", "\u200d", "\ufeff"]
NULL_MARKERS = ["", "null", "NULL", "None", "NA", " na "]
PLANS = ["free", "basic", "premium"]
CATEGORIES = ["food", "transport", "utilities", "shopping", "entertainment"]

random.seed(1337)

ROOT = Path(__file__).resolve().parent
USERS_PATH = ROOT / "users.csv"
TX_PATH = ROOT / "transactions.csv"


def zw_wrap(s):
    if random.random() < 0.35:
        return random.choice(ZERO_WIDTHS) + s
    if random.random() < 0.35:
        return s + random.choice(ZERO_WIDTHS)
    return s


def dirty_text(s):
    s = str(s)
    if random.random() < 0.45:
        s = " " * random.randint(0, 2) + s + " " * random.randint(0, 2)
    if random.random() < 0.35:
        s = zw_wrap(s)
    return s


def maybe_null(s):
    if random.random() < 0.03:
        return random.choice(NULL_MARKERS)
    return s


def fmt_amount_positive(value):
    value = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    styles = [
        lambda v: f"{v:.2f}",
        lambda v: f"${v:.2f}",
        lambda v: f"{v:,.2f}",
        lambda v: f" ${v:,.2f} ",
    ]
    return random.choice(styles)(value)


def fmt_amount_negative(value):
    value = Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    styles = [
        lambda v: f"-{v:.2f}",
        lambda v: f"(${v:.2f})",
        lambda v: f" -{v:,.2f} ",
    ]
    return random.choice(styles)(value)


def random_2024_date():
    start = date(2024, 1, 1)
    d = start + timedelta(days=random.randint(0, 365 - 1))
    styles = [
        d.strftime("%Y-%m-%d"),
        d.strftime("%Y/%m/%d"),
        d.strftime("%m/%d/%Y"),
    ]
    return random.choice(styles)


def invalid_date():
    return random.choice(
        [
            "2023-12-31",
            "2025-01-01",
            "2024-02-30",
            "13/01/2024",
            "2024/14/01",
            "not-a-date",
            "",
        ]
    )


def write_users():
    rows = []
    for i in range(1, 501):
        rows.append(
            {
                "id": dirty_text(str(i)),
                "name": dirty_text(f"User_{i:03d}"),
                "email": dirty_text(f"user{i}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )

    # Add duplicate rows; last valid row should win
    dup_ids = random.sample(range(1, 501), 80)
    for uid in dup_ids[:40]:
        rows.append(
            {
                "id": dirty_text(str(uid)),
                "name": dirty_text(f"User_{uid:03d}_OLD"),
                "email": dirty_text(f"old_user{uid}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )
        rows.append(
            {
                "id": dirty_text(str(uid)),
                "name": dirty_text(f"User_{uid:03d}"),
                "email": dirty_text(f"user{uid}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )

    # Add invalid rows
    for _ in range(25):
        rows.append(
            {
                "id": random.choice(["x", " ", "10.5", "ID7", ""]),
                "name": random.choice(["BadUser", "", "  ", "\u200b"]),
                "email": dirty_text("bad@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )

    # Add rows with valid id but invalid name; should be ignored
    for uid in random.sample(range(1, 501), 20):
        rows.append(
            {
                "id": dirty_text(str(uid)),
                "name": random.choice(["", " ", "\u200b", " NA "]),
                "email": dirty_text(f"broken{uid}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )

    random.shuffle(rows)
    # Ensure some duplicates truly have "last valid row wins"
    for uid in dup_ids[40:]:
        rows.append(
            {
                "id": dirty_text(str(uid)),
                "name": dirty_text(f"User_{uid:03d}_TEMP"),
                "email": dirty_text(f"temp{uid}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )
        rows.append(
            {
                "id": dirty_text(str(uid)),
                "name": dirty_text(f"User_{uid:03d}"),
                "email": dirty_text(f"user{uid}@example.com"),
                "plan": dirty_text(random.choice(PLANS)),
            }
        )

    with USERS_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["id", "name", "email", "plan"])
        writer.writeheader()
        writer.writerows(rows)


def write_transactions():
    rows = []
    tx_id = 1

    # Valid spend transactions
    for _ in range(6000):
        uid = random.randint(1, 500)
        amount = Decimal(random.randint(150, 250000)) / Decimal("100")
        rows.append(
            {
                "id": dirty_text(str(tx_id)),
                "user_id": dirty_text(str(uid)),
                "amount": dirty_text(fmt_amount_positive(amount)),
                "date": dirty_text(random_2024_date()),
                "category": dirty_text(random.choice(CATEGORIES)),
            }
        )
        tx_id += 1

    # Negative/refund/reversal/chargeback rows
    for _ in range(900):
        uid = random.randint(1, 500)
        amount = Decimal(random.randint(100, 50000)) / Decimal("100")
        rows.append(
            {
                "id": dirty_text(str(tx_id)),
                "user_id": dirty_text(str(uid)),
                "amount": dirty_text(fmt_amount_negative(amount)),
                "date": dirty_text(random_2024_date()),
                "category": dirty_text(random.choice(CATEGORIES + ["refund", "reversal", "chargeback"])),
            }
        )
        tx_id += 1

    # Positive amounts but refund-like categories
    for _ in range(500):
        uid = random.randint(1, 500)
        amount = Decimal(random.randint(100, 50000)) / Decimal("100")
        rows.append(
            {
                "id": dirty_text(str(tx_id)),
                "user_id": dirty_text(str(uid)),
                "amount": dirty_text(fmt_amount_positive(amount)),
                "date": dirty_text(random_2024_date()),
                "category": dirty_text(random.choice(["refund", "reversal", "chargeback"])),
            }
        )
        tx_id += 1

    # Invalid dates
    for _ in range(500):
        uid = random.randint(1, 500)
        amount = Decimal(random.randint(100, 50000)) / Decimal("100")
        rows.append(
            {
                "id": dirty_text(str(tx_id)),
                "user_id": dirty_text(str(uid)),
                "amount": dirty_text(fmt_amount_positive(amount)),
                "date": dirty_text(invalid_date()),
                "category": dirty_text(random.choice(CATEGORIES)),
            }
        )
        tx_id += 1

    # Invalid users / malformed amounts
    bad_amounts = ["abc", "", "12..34", "$", "1,2,3", "None", "NA"]
    bad_users = ["", "x", "10.5", "9999", "  ", "NULL"]
    for _ in range(400):
        rows.append(
            {
                "id": dirty_text(str(tx_id)),
                "user_id": dirty_text(random.choice(bad_users)),
                "amount": dirty_text(random.choice(bad_amounts)),
                "date": dirty_text(random.choice([random_2024_date(), invalid_date()])),
                "category": dirty_text(random.choice(CATEGORIES)),
            }
        )
        tx_id += 1

    random.shuffle(rows)

    with TX_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f, fieldnames=["id", "user_id", "amount", "date", "category"]
        )
        writer.writeheader()
        writer.writerows(rows)


def main():
    write_users()
    write_transactions()
    print("Generated users.csv and transactions.csv")


if __name__ == "__main__":
    main()