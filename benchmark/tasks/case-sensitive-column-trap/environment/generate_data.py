"""Generate fixture CSVs for T5: case-sensitive-column-trap.

Creates two CSVs:
  - public_data.csv: Title Case columns (Id, Name, Amount, Date) in that order
  - hidden_data.csv: Same Title Case columns but DIFFERENT order (Name, Date, Amount, Id)

The instructions reference lowercase column names ("amount").
If agent uses df.iloc[:,2] it works on public (Amount at index 2) but fails on hidden
(Amount at index 2 in hidden is actually Amount, but column order differs).

Actually the trap is more subtle: instructions say "amount" but CSV has "Amount".
Using df["amount"] raises KeyError. Agent must normalize to .lower().
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(555)

NAMES = [
    "Aria Chen", "Blake Rivera", "Carmen Diaz", "Derek Patel",
    "Elena Volkov", "Felix Tanaka", "Gina Rossi", "Hugo Larsson",
    "Isla Murphy", "Javier Cruz", "Kira Yamamoto", "Liam O'Brien",
    "Maya Singh", "Noah Fischer", "Priya Sharma", "Quinn Bailey",
    "Rosa Mendez", "Soren Andersen", "Tala Nguyen", "Uri Goldberg",
]

BASE_DATE = datetime(2024, 1, 1)

out_dir = os.path.dirname(os.path.abspath(__file__))

# Public CSV: columns in order (Id, Name, Amount, Date)
public_path = os.path.join(out_dir, "sales_data.csv")
rows_public = []
for i in range(1, 1501):
    name = random.choice(NAMES)
    amount = round(random.uniform(25.0, 8000.0), 2)
    date = (BASE_DATE + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")
    rows_public.append([i, name, amount, date])

with open(public_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Id", "Name", "Amount", "Date"])
    for row in rows_public:
        writer.writerow(row)

print(f"Generated {public_path} with {len(rows_public)} rows (Id, Name, Amount, Date)")

# Hidden CSV: SAME data but DIFFERENT column order (Name, Date, Amount, Id)
# This is used by the hidden verifier to test robustness
hidden_path = os.path.join(out_dir, "sales_data_hidden.csv")
with open(hidden_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["Name", "Date", "Amount", "Id"])
    for row in rows_public:
        # Reorder: Name, Date, Amount, Id
        writer.writerow([row[1], row[3], row[2], row[0]])

print(f"Generated {hidden_path} with {len(rows_public)} rows (Name, Date, Amount, Id)")
