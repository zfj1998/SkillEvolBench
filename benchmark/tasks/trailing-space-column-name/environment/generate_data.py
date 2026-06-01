"""Generate fixture CSV for T1: trailing-space-column-name.

Creates a 1000-row CSV with invisible whitespace in column names:
  - "  id"      (2 leading spaces)
  - "name"      (clean)
  - "amount "   (1 trailing space)
  - "date"      (clean)
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(42)

NAMES = [
    "Alice Johnson", "Bob Smith", "Carol Williams", "David Brown",
    "Eva Martinez", "Frank Garcia", "Grace Lee", "Henry Wilson",
    "Irene Anderson", "James Thomas", "Karen Jackson", "Leo White",
    "Maria Harris", "Nathan Clark", "Olivia Lewis", "Peter Robinson",
    "Quinn Walker", "Rachel Hall", "Samuel Allen", "Tina Young",
    "Uma King", "Victor Wright", "Wendy Scott", "Xavier Torres",
    "Yolanda Adams", "Zachary Nelson", "Abigail Hill", "Benjamin Moore",
    "Charlotte Taylor", "Daniel Martin",
]

BASE_DATE = datetime(2024, 1, 1)

out_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(out_dir, "sales.csv")

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    # Column names with invisible whitespace traps
    writer.writerow(["  id", "name", "amount ", "date"])
    for i in range(1, 1001):
        name = random.choice(NAMES)
        amount = round(random.uniform(10.0, 5000.0), 2)
        date = (BASE_DATE + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")
        writer.writerow([i, name, amount, date])

print(f"Generated {out_path} with 1000 rows")
