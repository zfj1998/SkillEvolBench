"""Generate fixture CSV for T2: latin1-bom-zwsp-encoding-chaos.

Creates a CSV with:
  - UTF-8 BOM (byte order mark) at start of file
  - German names with umlauts (Muller -> Mueller etc.)
  - ZWSP (zero-width space U+200B) injected into amount values
  - Normal column names: region, name, amount, quarter
"""

import os
import random

random.seed(73)

REGIONS = ["Bavaria", "Hesse", "Saxony", "Berlin", "Hamburg"]

GERMAN_NAMES = [
    "M\u00fcller", "K\u00f6hler", "Sch\u00e4fer", "Wei\u00df", "Kr\u00fcger",
    "B\u00f6hm", "G\u00fcnther", "Schr\u00f6der", "J\u00e4ger", "V\u00f6lker",
    "St\u00f6hr", "L\u00f6ffler", "H\u00fcbner", "K\u00e4stner", "Gr\u00fcn",
    "F\u00f6rster", "B\u00fcrger", "Z\u00f6ller", "Br\u00fcckner", "D\u00fcrr",
]

QUARTERS = ["Q1", "Q2", "Q3", "Q4"]

ZWSP = "\u200B"  # zero-width space

out_dir = os.path.dirname(os.path.abspath(__file__))
out_path = os.path.join(out_dir, "revenue.csv")

rows = []
for i in range(1, 801):
    region = random.choice(REGIONS)
    name = random.choice(GERMAN_NAMES)
    amount = round(random.uniform(100.0, 25000.0), 2)
    quarter = random.choice(QUARTERS)

    # Inject ZWSP into ~40% of amount values (makes them unparseable as float)
    amount_str = f"{amount}"
    if random.random() < 0.40:
        # Insert ZWSP at random position within the number string
        pos = random.randint(1, len(amount_str) - 1)
        amount_str = amount_str[:pos] + ZWSP + amount_str[pos:]

    rows.append((region, name, amount_str, quarter))

# Write with UTF-8 BOM
with open(out_path, "w", encoding="utf-8-sig", newline="") as f:
    f.write("region,name,amount,quarter\n")
    for region, name, amount_str, quarter in rows:
        f.write(f"{region},{name},{amount_str},{quarter}\n")

print(f"Generated {out_path} with {len(rows)} rows (UTF-8 BOM + ZWSP in amounts)")

# Verify BOM exists
with open(out_path, "rb") as f:
    header = f.read(3)
    assert header == b"\xef\xbb\xbf", "BOM not written!"
    print("Verified: UTF-8 BOM present")

# Count ZWSP occurrences
with open(out_path, "r", encoding="utf-8-sig") as f:
    content = f.read()
    zwsp_count = content.count(ZWSP)
    print(f"ZWSP occurrences: {zwsp_count}")
