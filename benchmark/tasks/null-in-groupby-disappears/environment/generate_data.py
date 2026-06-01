import csv
import random
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

random.seed(2025)

OUT = Path("regional_sales.csv")

REGION_VARIANTS = {
    "East": [
        "East", " east", "EAST ", "e", "E", "eastern", "Ｅａｓｔ",
        "\ufeffEast", "East\u200b", " east\u2060 "
    ],
    "West": [
        "West", " west ", "WEST", "w", "W", "western", "Ｗｅｓｔ",
        "\ufeffWest", "West\u200b", " west\u2060 "
    ],
    "North": [
        "North", " north ", "NORTH", "n", "N", "northern", "Ｎｏｒｔｈ",
        "\ufeffNorth", "North\u200b", " north\u2060 "
    ],
    "South": [
        "South", " south ", "SOUTH", "s", "S", "southern", "Ｓｏｕｔｈ",
        "\ufeffSouth", "South\u200b", " south\u2060 "
    ],
    "Unknown": [
        "", " ", "   ", "\u200b", "\ufeff", "null", "NULL", "None",
        "n/a", "NA", "unk", "unknown", " UnKnown "
    ],
}

PRODUCTS = ["Widget", "Gadget", "Thingamajig", "Doohickey"]
CANONICALS = ["East", "West", "North", "South", "Unknown"]


def rand_date():
    month = random.randint(1, 12)
    day = random.randint(1, 28)
    return f"2024-{month:02d}-{day:02d}"


def money_str(cents: int, style: int) -> str:
    amt = Decimal(cents) / Decimal("100")
    neg = amt < 0
    abs_amt = -amt if neg else amt
    s = f"{abs_amt.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):,.2f}"
    if style == 0:
        out = s.replace(",", "")
    elif style == 1:
        out = s
    elif style == 2:
        out = f"${s}"
    elif style == 3:
        out = f" {s} "
    elif style == 4:
        out = f"+{s}" if not neg else f"-{s}"
        return out
    else:
        out = s.replace(",", "")
    if neg:
        if style in (2, 3):
            return f"({out.strip('$ ')})" if style == 3 else f"(${s})"
        return f"({s})"
    return out


def choose_region_variant(canonical):
    return random.choice(REGION_VARIANTS[canonical])


rows = []
sale_id = 1

# Base rows
for _ in range(6200):
    canonical = random.choices(
        CANONICALS, weights=[22, 22, 20, 20, 16], k=1
    )[0]
    cents = random.randint(500, 250000)
    if random.random() < 0.06:
        cents *= -1
    amount = money_str(cents, random.randint(0, 4))
    rows.append(
        {
            "sale_id": str(sale_id),
            "region": choose_region_variant(canonical),
            "product": random.choice(PRODUCTS),
            "amount": amount,
            "date": rand_date(),
            "notes": random.choice(["", "ok", "import", "legacy", ""]),
        }
    )
    sale_id += 1

# Add duplicate sale_ids with conflicting rows
duplicate_ids = random.sample(range(1, sale_id), 900)
for dup_id in duplicate_ids:
    original = rows[dup_id - 1]
    canonical = random.choice(CANONICALS)
    # sometimes better parseable, sometimes bad, sometimes larger abs amount
    mode = random.random()
    if mode < 0.25:
        amount = "bad-data"
    elif mode < 0.5:
        cents = random.randint(100, 300000)
        if random.random() < 0.15:
            cents *= -1
        amount = money_str(cents, random.randint(0, 4))
    elif mode < 0.75:
        # same magnitude tie candidate
        base = original["amount"]
        amount = base
    else:
        cents = random.randint(300001, 500000)
        if random.random() < 0.2:
            cents *= -1
        amount = money_str(cents, random.randint(0, 4))
    rows.append(
        {
            "sale_id": str(dup_id),
            "region": choose_region_variant(canonical),
            "product": random.choice(PRODUCTS),
            "amount": amount,
            "date": rand_date(),
            "notes": random.choice(["dup", "reingest", "retry", ""]),
        }
    )

# Add rows with unparseable amounts
bad_amounts = ["", " ", "N/A", "null", "1.2.3", "$$", "12,34,56", "abc", "--5", "(12.3"]
for _ in range(350):
    rows.append(
        {
            "sale_id": str(sale_id),
            "region": choose_region_variant(random.choice(CANONICALS)),
            "product": random.choice(PRODUCTS),
            "amount": random.choice(bad_amounts),
            "date": rand_date(),
            "notes": "bad_amount",
        }
    )
    sale_id += 1

# Add unknown weird region labels that should map to Unknown
weird_regions = ["Northeast", "SW", "central", "region-1", "??", "east-west", "0"]
for _ in range(250):
    cents = random.randint(100, 100000)
    rows.append(
        {
            "sale_id": str(sale_id),
            "region": random.choice(weird_regions),
            "product": random.choice(PRODUCTS),
            "amount": money_str(cents, random.randint(0, 4)),
            "date": rand_date(),
            "notes": "weird_region",
        }
    )
    sale_id += 1

with OUT.open("w", newline="", encoding="utf-8") as f:
    writer = csv.DictWriter(
        f, fieldnames=["sale_id", "region", "product", "amount", "date", "notes"]
    )
    writer.writeheader()
    writer.writerows(rows)

print(f"Wrote {len(rows)} rows to {OUT}")