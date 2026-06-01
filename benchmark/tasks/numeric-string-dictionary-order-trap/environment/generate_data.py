"""Generate 500-product CSV with string product_ids.
IDs 1-99 have leading zeros ("001"-"099"), IDs 100-500 are plain ("100"-"500").
String sorting gives "001","010","011",...,"099","1","10","100",...
which is wrong. Correct order: 1,2,...,500 (or 001,...,500 numerically)."""

import csv
import random

random.seed(99)

CATEGORIES = ["Electronics", "Clothing", "Home & Garden", "Sports", "Books",
              "Toys", "Food & Beverage", "Health", "Automotive", "Office"]

ADJECTIVES = ["Premium", "Basic", "Professional", "Compact", "Ultra",
              "Deluxe", "Standard", "Advanced", "Classic", "Modern"]

NOUNS = ["Widget", "Gadget", "Device", "Tool", "Kit", "Set", "Pack",
         "Bundle", "System", "Unit", "Module", "Component", "Accessory"]

rows = []
# TRAP DESIGN: Most IDs are plain strings without leading zeros ("1"-"500").
# A few legacy IDs (7,13,42,56,88) have leading zeros ("007","013","042","056","088").
# String sort gives: "1","10","100","11",...,"19","2","20",...,"9","99"
# Natural sort gives: "1","2",...,"9","10","11",...,"99","100",...,"500"
LEGACY_IDS = {7, 13, 42, 56, 88}

for i in range(1, 501):
    if i in LEGACY_IDS:
        product_id = f"{i:03d}"  # "007", "013", "042", "056", "088"
    else:
        product_id = str(i)  # "1", "2", ..., "500" (NO leading zeros)

    name = f"{random.choice(ADJECTIVES)} {random.choice(NOUNS)} {random.choice(['A','B','C','X','Z'])}-{random.randint(1,99)}"
    price = round(random.uniform(5.99, 999.99), 2)
    stock = random.randint(0, 500)
    category = random.choice(CATEGORIES)
    weight_kg = round(random.uniform(0.1, 25.0), 2)
    rating = round(random.uniform(1.0, 5.0), 1)

    rows.append({
        "product_id": product_id,
        "name": name,
        "category": category,
        "price": f"{price:.2f}",
        "stock_quantity": stock,
        "weight_kg": f"{weight_kg:.2f}",
        "avg_rating": rating,
    })

# Shuffle rows so they're not in any order
random.shuffle(rows)

with open("products.csv", "w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(f, fieldnames=["product_id", "name", "category",
                                            "price", "stock_quantity",
                                            "weight_kg", "avg_rating"])
    writer.writeheader()
    writer.writerows(rows)

print(f"Generated products.csv with {len(rows)} rows")

# Verify the trap: show first 15 items under string sort vs numeric sort
string_sorted = sorted([r["product_id"] for r in rows])
numeric_sorted = sorted([r["product_id"] for r in rows], key=lambda x: int(x))
print(f"String sort first 15: {string_sorted[:15]}")
print(f"Numeric sort first 15: {numeric_sorted[:15]}")
