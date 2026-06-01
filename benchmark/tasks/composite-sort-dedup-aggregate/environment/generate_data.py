"""Generate composite transaction log with multiple traps:
- Dates in M/D/YYYY format (string sort pitfall)
- String product IDs with leading zeros (numeric sort pitfall)
- Comma-formatted amounts ("$1,234.56") that need cleaning
- ~5% duplicate rows (exact duplicates)
- Task: clean, sort, dedup, aggregate by product+date
"""

import csv
import random
from datetime import datetime, timedelta

random.seed(314)

# Variable-width product IDs: P1-P9 (no padding) + P10-P50 (no padding)
# String sort gives P1,P10,P11,...,P19,P2,P20,...  (wrong)
# Natural sort gives P1,P2,...,P9,P10,P11,...,P50  (correct)
PRODUCTS = [f"P{i}" for i in range(1, 51)]  # P1 to P50

START = datetime(2024, 1, 1)
END = datetime(2024, 6, 30)
DELTA = (END - START).days

CUSTOMERS = [f"CUST-{i:04d}" for i in range(1, 201)]
CHANNELS = ["online", "in-store", "phone", "wholesale"]

rows = []
for i in range(800):
    dt = START + timedelta(days=random.randint(0, DELTA))

    # Date in M/D/YYYY format (trap 1: string sort pitfall)
    if random.random() < 0.65:
        date_str = f"{dt.month}/{dt.day}/{dt.year}"
    else:
        date_str = dt.strftime("%m/%d/%Y")

    product = random.choice(PRODUCTS)
    amount = round(random.uniform(10.0, 5000.0), 2)

    # Format amount with commas and dollar sign (trap 3: needs cleaning)
    if amount >= 1000:
        amount_str = f"${amount:,.2f}"  # e.g., "$1,234.56"
    else:
        amount_str = f"${amount:.2f}"   # e.g., "$45.99"

    quantity = random.randint(1, 20)

    rows.append({
        "transaction_id": f"TXN-{i+1:05d}",
        "date": date_str,
        "product_id": product,
        "customer_id": random.choice(CUSTOMERS),
        "amount": amount_str,
        "quantity": quantity,
        "channel": random.choice(CHANNELS),
    })

# Insert ~5% exact duplicates (trap 4: dedup needed)
n_dupes = 40
dupe_indices = random.sample(range(len(rows)), n_dupes)
duplicates = []
for idx in dupe_indices:
    dupe = dict(rows[idx])
    # Give duplicate a new transaction_id to make it subtle
    dupe["transaction_id"] = f"TXN-{800 + len(duplicates) + 1:05d}"
    duplicates.append(dupe)

rows.extend(duplicates)
random.shuffle(rows)

# Re-number transaction IDs after shuffle
for i, row in enumerate(rows):
    row["transaction_id"] = f"TXN-{i+1:05d}"

with open("transaction_log.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["transaction_id", "date", "product_id",
                                            "customer_id", "amount", "quantity", "channel"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated transaction_log.csv with {len(rows)} rows ({n_dupes} duplicates)")
