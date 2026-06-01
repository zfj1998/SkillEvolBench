"""Generate fixture CSV for T3: mixed-type-column-chaos.

Creates a 5000-row CSV where the 'revenue' column has 5 format types:
  - 60% normal float: "1234.56"
  - 15% comma-formatted: "1,234.56"
  - 10% dollar-prefixed: "$1234.56"
  - 10% N/A or null: "N/A", "", "null", "n/a", "-"
  - 5% accounting negative: "(1234.56)"
"""

import csv
import os
import random
from datetime import datetime, timedelta

random.seed(99)

PRODUCTS = [
    "Widget Alpha", "Widget Beta", "Widget Gamma", "Gadget Pro",
    "Gadget Lite", "Sensor X1", "Sensor X2", "Module A",
    "Module B", "Component Z", "Assembly Kit", "Power Unit",
    "Control Board", "Display Panel", "Connector Set",
]

CATEGORIES = ["Electronics", "Hardware", "Software", "Services", "Consulting"]

NULL_VALUES = ["N/A", "", "null", "n/a", "-"]
BASE_DATE = datetime(2024, 1, 1)

out_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(out_dir, "transactions.csv")

rows = []
for i in range(1, 5001):
    product = random.choice(PRODUCTS)
    category = random.choice(CATEGORIES)
    date = (BASE_DATE + timedelta(days=random.randint(0, 364))).strftime("%Y-%m-%d")

    # Generate a base amount
    base_amount = round(random.uniform(50.0, 15000.0), 2)

    # Determine format type
    r = random.random()
    if r < 0.60:
        # Normal float
        revenue_str = f"{base_amount}"
    elif r < 0.75:
        # Comma-formatted
        revenue_str = f"{base_amount:,.2f}"
    elif r < 0.85:
        # Dollar-prefixed
        revenue_str = f"${base_amount}"
    elif r < 0.95:
        # N/A or null
        revenue_str = random.choice(NULL_VALUES)
    else:
        # Accounting negative: (amount)
        revenue_str = f"({base_amount})"

    rows.append([i, product, category, revenue_str, date])

with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["id", "product", "category", "revenue", "date"])
    for row in rows:
        writer.writerow(row)

# Count format types
format_counts = {"normal": 0, "comma": 0, "dollar": 0, "null": 0, "accounting": 0}
for row in rows:
    val = row[3]
    if val in NULL_VALUES:
        format_counts["null"] += 1
    elif val.startswith("(") and val.endswith(")"):
        format_counts["accounting"] += 1
    elif val.startswith("$"):
        format_counts["dollar"] += 1
    elif "," in val:
        format_counts["comma"] += 1
    else:
        format_counts["normal"] += 1

print(f"Generated {out_path} with {len(rows)} rows")
print(f"Format distribution: {format_counts}")
