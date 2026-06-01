"""Generate fixture for T6: full-schema-inspect-clean-query-validate.

Creates a "dirty CSV" combining problems from T1-T3:
  - UTF-8 BOM
  - Trailing/leading spaces in column names
  - ZWSP in amount values
  - Mixed-type amounts (normal, comma, dollar, accounting, null)
Plus an expected_totals.json for validation.
"""

import csv
import json
import os
import random
from datetime import datetime, timedelta

random.seed(777)

REGIONS = ["APAC", "EMEA", "LATAM", "AMER"]
DEPARTMENTS = ["Sales", "Marketing", "Engineering", "Support", "Operations"]
NAMES = [
    "Aiko Tanaka", "Boris Petrov", "Camille Dubois", "Dmitri Volkov",
    "Elena Rodriguez", "Fatima Al-Hassan", "Giovanni Rossi", "Hana Kim",
    "Ivan Novak", "Julia Santos", "Kenji Yamamoto", "Lucia Fernandez",
    "Marcus Weber", "Nadia Okafor", "Omar Benali", "Priya Patel",
    "Ravi Sharma", "Sofia Andersson", "Tomasz Kowalski", "Uma Krishnan",
]

ZWSP = "\u200B"
NULL_VALUES = ["N/A", "", "null", "n/a", "-"]
BASE_DATE = datetime(2024, 1, 1)

out_dir = os.path.dirname(os.path.abspath(__file__))
csv_path = os.path.join(out_dir, "dirty_data.csv")

# Column names with whitespace traps
COL_ID = "  id"           # leading spaces
COL_NAME = "name"         # clean
COL_REGION = "region "    # trailing space
COL_DEPT = " department"  # leading space
COL_AMOUNT = "amount  "   # trailing spaces
COL_DATE = "date"         # clean

rows_raw = []   # for CSV writing
rows_clean = [] # for expected totals computation

for i in range(1, 2001):
    name = random.choice(NAMES)
    region = random.choice(REGIONS)
    dept = random.choice(DEPARTMENTS)
    date = (BASE_DATE + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")

    base_amount = round(random.uniform(50.0, 20000.0), 2)

    # Determine format type
    r = random.random()
    if r < 0.45:
        # Normal float
        amount_str = f"{base_amount}"
        clean_amount = base_amount
    elif r < 0.60:
        # Comma-formatted
        amount_str = f"{base_amount:,.2f}"
        clean_amount = base_amount
    elif r < 0.70:
        # Dollar-prefixed
        amount_str = f"${base_amount}"
        clean_amount = base_amount
    elif r < 0.80:
        # Accounting negative
        amount_str = f"({base_amount})"
        clean_amount = -base_amount
    elif r < 0.90:
        # N/A or null
        amount_str = random.choice(NULL_VALUES)
        clean_amount = None
    else:
        # Normal float with ZWSP injected
        amount_str = f"{base_amount}"
        pos = random.randint(1, len(amount_str) - 1)
        amount_str = amount_str[:pos] + ZWSP + amount_str[pos:]
        clean_amount = base_amount

    rows_raw.append([i, name, region, dept, amount_str, date])
    rows_clean.append({
        "name": name,
        "region": region,
        "department": dept,
        "amount": clean_amount,
        "date": date,
    })

# Write CSV with BOM + dirty column names
with open(csv_path, "w", encoding="utf-8-sig", newline="") as f:
    f.write(f"{COL_ID},{COL_NAME},{COL_REGION},{COL_DEPT},{COL_AMOUNT},{COL_DATE}\n")
    writer = csv.writer(f)
    for row in rows_raw:
        writer.writerow(row)

print(f"Generated {csv_path} with {len(rows_raw)} rows")

# Verify BOM
with open(csv_path, "rb") as f:
    assert f.read(3) == b"\xef\xbb\xbf", "BOM missing!"

# Compute expected totals per region
region_totals = {}
for row in rows_clean:
    if row["amount"] is not None:
        r = row["region"]
        region_totals[r] = region_totals.get(r, 0.0) + row["amount"]

expected_totals = {}
for r in sorted(region_totals.keys()):
    expected_totals[r] = round(region_totals[r], 2)

# Write expected_totals.json
totals_path = os.path.join(out_dir, "expected_totals.json")
with open(totals_path, "w") as f:
    json.dump(expected_totals, f, indent=2)

print(f"Generated {totals_path}")
print(f"Expected totals: {expected_totals}")

# Count format types
zwsp_count = sum(1 for row in rows_raw if ZWSP in str(row[4]))
null_count = sum(1 for row in rows_clean if row["amount"] is None)
neg_count = sum(1 for row in rows_raw if str(row[4]).startswith("("))
dollar_count = sum(1 for row in rows_raw if str(row[4]).startswith("$"))
comma_count = sum(1 for row in rows_raw if "," in str(row[4]) and not str(row[4]).startswith("("))
print(f"ZWSP: {zwsp_count}, Null: {null_count}, Neg: {neg_count}, Dollar: {dollar_count}, Comma: {comma_count}")
