import csv
import os
import random

random.seed(7)

OUT_2023 = "sales_2023.csv"
OUT_2024 = "sales_2024.csv"

ZWSP = "\u200b"
NBSP = "\u00a0"

BASE_PRODUCTS = [
    ("Ultra HD Smart Television 55-inch", "Electronics", 184655.32, 201719.02),
    ("Wireless Bluetooth Noise-Cancelling Headphones", "Audio", 413348.03, 478539.04),
    ("Professional Grade DSLR Camera Body", "Electronics", 89238.76, 86148.56),
    ("Portable External SSD 1TB", "Computing", 77894.46, 108499.47),
    ("Ergonomic Mechanical Gaming Keyboard", "Computing", 256372.79, 367402.58),
    ("High-Performance Gaming Laptop 16-inch", "Computing", 348270.85, 324620.48),
    ("Smart Home Security Camera System", "Home", 45061.68, 41441.19),
    ("Premium Espresso Coffee Machine", "Home", 19335.78, 23190.76),
    ("Wireless Charging Pad Multi-Device", "Accessories", 157869.42, 184884.82),
    ("Noise-Cancelling True Wireless Earbuds", "Audio", 477608.03, 504069.64),
    ("Product 11", "Accessories", 450900.22, 561834.29),
    ("Product 12", "Computing", 126674.43, 107731.15),
    ("Product 13", "Audio", 78910.12, 75910.68),
    ("Product 14", "Computing", 127406.27, 156291.71),
    ("Product 15", "Computing", 84251.35, 114377.73),
    ("Product 16", "Electronics", 141309.57, 172585.22),
    ("Product 17", "Accessories", 35679.94, 35569.47),
    ("Product 18", "Accessories", 302749.21, 409147.60),
    ("Product 19", "Home", 454207.52, 505877.55),
    ("Product 20", "Accessories", 187633.87, 251528.51),
    ("Product 21", "Electronics", 243611.35, 332123.00),
    ("Product 22", "Electronics", 496379.76, 421449.29),
    ("Product 23", "Electronics", 283573.10, 232838.87),
    ("Product 24", "Electronics", 446866.10, 591555.75),
    ("Product 25", "Audio", 425617.60, 432517.92),
    ("Product 26", "Computing", 208516.78, 294045.72),
    ("Product 27", "Computing", 153536.01, 185551.71),
    ("Product 28", "Home", 234621.47, 346627.52),
    ("Product 29", "Home", 260783.09, 303427.71),
    ("Product 30", "Electronics", 335963.63, 461210.74),
    ("Product 31", "Audio", 414264.06, 542986.46),
    ("Product 32", "Audio", 287721.87, 372878.26),
    ("Product 33", "Audio", 102331.40, 92058.32),
    ("Product 34", "Audio", 176569.84, 160436.58),
    ("Product 35", "Home", 0.00, 15000.00),
    ("Product 36", "Home", 0.00, 0.00),
    ("Widget Pro IV", "Computing", 100000.00, 130000.00),
    ("Gadget & Gear", "Accessories", 50000.00, 43000.00),
    ("Alpha/Beta Device", "Electronics", 75000.00, 76000.00),
    ("Legacy Camera (Mk II)", "Electronics", 120000.00, 90000.00),
    ("Unmatched Only 2023", "Misc", 33333.33, None),
]

EXTRA_2024_ONLY = [
    ("Unmatched Only 2024", "Misc", 44444.44),
]

def fmt_money(v, style=0):
    if style == 0:
        return f"{v:.2f}"
    if style == 1:
        return f"{v:,.2f}"
    if style == 2:
        return f"${v:,.2f}"
    if style == 3:
        return f"  {v:,.2f}  "
    return f"{v:.2f}"

def split_amount(total):
    if total == 0:
        return [0.0, 0.0]
    a = round(total * 0.37, 2)
    b = round(total - a, 2)
    return [a, b]

def name_variant(name, year, idx):
    variants = {
        "Ultra HD Smart Television 55-inch": [
            " Ultra  HD Smart Television 55-inch ",
            f"Ultra HD Smart Television 55{ZWSP}-inch",
            "ultra hd smart television 55 inch",
            "ULTRA_HD_SMART_TELEVISION_55-INCH",
        ],
        "Wireless Bluetooth Noise-Cancelling Headphones": [
            "Wireless Bluetooth Noise Cancelling Headphones",
            "wireless bluetooth noise-cancelling headphones",
            f"Wireless Bluetooth Noise{ZWSP}-Cancelling Headphones",
        ],
        "Professional Grade DSLR Camera Body": [
            "Professional Grade DSLR Camera Body",
            "professional grade dslr camera body",
        ],
        "Portable External SSD 1TB": [
            "Portable External SSD 1TB",
            "Portable External SSD 1TB ",
        ],
        "Ergonomic Mechanical Gaming Keyboard": [
            "Ergonomic Mechanical Gaming Keyboard",
            "Ergonomic  Mechanical Gaming Keyboard",
        ],
        "High-Performance Gaming Laptop 16-inch": [
            "High-Performance Gaming Laptop 16-inch",
            "High Performance Gaming Laptop 16 inch",
        ],
        "Smart Home Security Camera System": [
            "Smart Home Security Camera System",
            "smart home security camera system",
        ],
        "Premium Espresso Coffee Machine": [
            "Premium Espresso Coffee Machine",
            "Premium Espresso Coffee Machine ",
        ],
        "Wireless Charging Pad Multi-Device": [
            "Wireless Charging Pad Multi-Device",
            "Wireless Charging Pad Multi Device",
        ],
        "Noise-Cancelling True Wireless Earbuds": [
            "Noise-Cancelling True Wireless Earbuds",
            "Noise Cancelling True Wireless Earbuds",
        ],
        "Widget Pro IV": [
            "Widget Pro IV",
            "widget pro iv",
        ],
        "Gadget & Gear": [
            "Gadget & Gear",
            "Gadget and Gear",
        ],
        "Alpha/Beta Device": [
            "Alpha/Beta Device",
            "Alpha Beta Device",
        ],
        "Legacy Camera (Mk II)": [
            "Legacy Camera (Mk II)",
            "Legacy Camera Mk II",
        ],
    }
    if year == 2024:
        variants_2024 = {
            "Ultra HD Smart Television 55-inch": [
                "ultra hd smart television 55-inch",
                "Ultra HD Smart Television 55 inch",
            ],
            "Wireless Bluetooth Noise-Cancelling Headphones": [
                "Wireless Bluetooth Noise-Cancelling Headphones",
                "Wireless Bluetooth Noise Cancelling Headphones",
            ],
            "Widget Pro IV": [
                "Widget Pro 4",
                "widget pro 4",
            ],
            "Gadget & Gear": [
                "Gadget and Gear",
                "Gadget & Gear",
            ],
            "Alpha/Beta Device": [
                "Alpha Beta Device",
                "Alpha/Beta Device",
            ],
            "Legacy Camera (Mk II)": [
                "Legacy Camera Mk 2",
                "Legacy Camera (Mk II)",
            ],
        }
        if name in variants_2024:
            return variants_2024[name][idx % len(variants_2024[name])]
    if name in variants:
        return variants[name][idx % len(variants[name])]
    if name.startswith("Product "):
        n = name.split()[-1]
        opts = [
            f"Product_{n}",
            f"product {n}",
            f" Product {n} ",
            f"Product{NBSP}{n}",
        ]
        return opts[idx % len(opts)]
    return name

def write_rows(path, rows):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["product_name", "category", "revenue", "units_sold", "notes", "snapshot_id"])
        writer.writerows(rows)

def main():
    rows_2023 = []
    rows_2024 = []

    snap = 1

    for i, (name, category, rev23, rev24) in enumerate(BASE_PRODUCTS):
        units23 = random.randint(100, 7000)
        if rev24 is not None:
            units24 = random.randint(100, 7000)

        if name in {
            "Ultra HD Smart Television 55-inch",
            "Wireless Bluetooth Noise-Cancelling Headphones",
            "Product 11",
            "Product 14",
            "Product 18",
            "Product 21",
            "Product 24",
            "Product 30",
            "Widget Pro IV",
            "Gadget & Gear",
            "Alpha/Beta Device",
            "Legacy Camera (Mk II)",
        }:
            parts23 = split_amount(rev23)
            parts24 = split_amount(rev24) if rev24 is not None else []
            for j, part in enumerate(parts23):
                rows_2023.append([
                    name_variant(name, 2023, j),
                    category if j == 0 else category + " ",
                    fmt_money(part, j % 4),
                    str(units23 // 2 if j == 0 else units23 - units23 // 2),
                    "duplicate export",
                    f"2023-{snap}",
                ])
                snap += 1
            if rev24 is not None:
                for j, part in enumerate(parts24):
                    rows_2024.append([
                        name_variant(name, 2024, j),
                        category.lower() if j == 0 else category,
                        fmt_money(part, (j + 1) % 4),
                        str(units24 // 2 if j == 0 else units24 - units24 // 2),
                        "duplicate export",
                        f"2024-{snap}",
                    ])
                    snap += 1
        else:
            rev23_text = fmt_money(rev23, i % 4)
            if name == "Product 35":
                rev23_text = "NA"
            elif name == "Product 36":
                rev23_text = ""
            rows_2023.append([
                name_variant(name, 2023, 0),
                category,
                rev23_text,
                str(units23),
                "",
                f"2023-{snap}",
            ])
            snap += 1

            if rev24 is not None:
                rev24_text = fmt_money(rev24, (i + 1) % 4)
                if name == "Product 36":
                    rev24_text = "null"
                rows_2024.append([
                    name_variant(name, 2024, 0),
                    category,
                    rev24_text,
                    str(units24),
                    "",
                    f"2024-{snap}",
                ])
                snap += 1

    rows_2023.append([
        f"{ZWSP}Product 12{ZWSP}",
        "Computing",
        "None",
        "bad",
        "placeholder duplicate should aggregate as zero",
        f"2023-{snap}",
    ])
    snap += 1

    rows_2024.append([
        "Product_33",
        "Audio",
        "(0.00)",
        "0",
        "zero adjustment row",
        f"2024-{snap}",
    ])
    snap += 1

    rows_2024.append([
        "Product_34",
        "Audio",
        "(5,000.00)",
        "10",
        "negative adjustment row",
        f"2024-{snap}",
    ])
    snap += 1

    for name, category, revenue in EXTRA_2024_ONLY:
        rows_2024.append([
            name,
            category,
            f"${revenue:,.2f}",
            "123",
            "",
            f"2024-{snap}",
        ])
        snap += 1

    os.makedirs(".", exist_ok=True)
    write_rows(OUT_2023, rows_2023)
    write_rows(OUT_2024, rows_2024)
    print("Generated sales_2023.csv and sales_2024.csv")

if __name__ == "__main__":
    main()