import csv
import os
import random

random.seed(1337)

PROJECT_DIR = "."
POP_PATH = os.path.join(PROJECT_DIR, "population.csv")
GDP_PATH = os.path.join(PROJECT_DIR, "gdp_data.csv")


CITIES = [
    ("New York", ["NY", "NYC", "New York City", "New\u200b York", "New York\u00a0City"]),
    ("Los Angeles", ["LA", "Los\u00a0Angeles", "Los-Angeles"]),
    ("Chicago", ["Chi", "Chicago"]),
    ("Houston", ["Hou", "Houston"]),
    ("Phoenix", ["Phx", "Phoenix"]),
    ("Philadelphia", ["Philly", "Philadelphia"]),
    ("San Antonio", ["SA", "San Antonio", "San\u200b Antonio"]),
    ("San Diego", ["SD", "San Diego"]),
    ("Dallas", ["Dal", "Dallas"]),
    ("San Jose", ["SJ", "San  Jose", "San-Jose"]),
    ("Austin", ["Aus", "Austin"]),
    ("Jacksonville", ["Jax", "Jacksonville"]),
    ("Fort Worth", ["FW", "Ft Worth", "Fort Worth"]),
    ("Columbus", ["Col", "Columbus"]),
    ("Charlotte", ["Char", "Charlotte"]),
    ("Indianapolis", ["Indy", "Indianapolis"]),
    ("San Francisco", ["SF", "San Francisco", "San\u00a0Francisco"]),
    ("Seattle", ["Sea", "Seattle"]),
    ("Denver", ["Den", "Denver"]),
    ("Washington", ["DC", "Washington, D.C.", "District of Columbia", "Washington"]),
    ("Nashville", ["Nashville"]),
    ("Oklahoma City", ["Oklahoma City", "Oklahoma\u00a0City"]),
    ("El Paso", ["El Paso", "El-Paso"]),
    ("Boston", ["Boston"]),
    ("Portland", ["Portland"]),
    ("Las Vegas", ["Las Vegas", "Las-Vegas"]),
    ("Memphis", ["Memphis"]),
    ("Louisville", ["Louisville"]),
    ("Baltimore", ["Baltimore"]),
    ("Milwaukee", ["Milwaukee"]),
    ("Albuquerque", ["Albuquerque"]),
    ("Tucson", ["Tucson"]),
    ("Fresno", ["Fresno"]),
    ("Mesa", ["Mesa"]),
    ("Sacramento", ["Sacramento"]),
    ("Atlanta", ["Atlanta"]),
    ("Kansas City", ["Kansas City"]),
    ("Colorado Springs", ["Colorado Springs"]),
    ("Miami", ["Miami"]),
    ("Raleigh", ["Raleigh"]),
    ("Omaha", ["Omaha"]),
    ("Long Beach", ["Long Beach"]),
    ("Virginia Beach", ["Virginia Beach"]),
    ("Oakland", ["Oakland"]),
    ("Minneapolis", ["Minneapolis"]),
    ("Tulsa", ["Tulsa"]),
    ("Arlington", ["Arlington"]),
    ("Tampa", ["Tampa"]),
    ("New Orleans", ["New Orleans", "New\u2019Orleans"]),
    ("Wichita", ["Wichita"]),
    ("St Louis", ["St. Louis", "Saint Louis", "St Louis"]),
    ("Cleveland", ["Cleveland"]),
]

INDUSTRIES = [
    "Tech", "Finance", "Healthcare", "Energy", "Manufacturing",
    "Logistics", "Tourism", "Education"
]


def fmt_int(n):
    style = random.choice(["plain", "comma", "space"])
    if style == "plain":
        return str(n)
    if style == "comma":
        return f"{n:,}"
    return f"  {n:,}  "


def fmt_float(n):
    style = random.choice(["plain", "currency", "space"])
    if style == "plain":
        return f"{n:.1f}"
    if style == "currency":
        return f"${n:.1f}"
    return f"  {n:.1f}  "


def fmt_pct(n):
    style = random.choice(["plain", "percent", "space"])
    if style == "plain":
        return f"{n:.1f}"
    if style == "percent":
        return f"{n:.1f}%"
    return f"  {n:.1f}%  "


def maybe_dirty_null():
    return random.choice(["NA", "N/A", "null", "None", "", "—"])


def truthy_str():
    return random.choice(["1", "true", "TRUE", "yes", "Yes"])


def write_population():
    rows = []
    for idx, (canon, aliases) in enumerate(CITIES, start=1):
        pop = 200000 + idx * 137531
        area = 100 + (idx * 29) % 1400

        base_city = canon
        rows.append({
            "city": base_city,
            "country": "US",
            "population": fmt_int(pop),
            "area_sqkm": str(area),
            "is_test": "",
            "note": ""
        })

        if idx % 4 == 0:
            alias = aliases[min(1, len(aliases) - 1)]
            rows.append({
                "city": alias,
                "country": "US",
                "population": fmt_int(pop + random.randint(1, 999)),
                "area_sqkm": str(area + random.randint(0, 5)),
                "is_test": "",
                "note": "dup alias"
            })

        if idx % 7 == 0:
            alias = aliases[-1]
            rows.append({
                "city": alias,
                "country": "US",
                "population": maybe_dirty_null(),
                "area_sqkm": str(area + 1),
                "is_test": "",
                "note": "bad population duplicate"
            })

    rows.extend([
        {"city": "# training row", "country": "US", "population": "999999", "area_sqkm": "1", "is_test": "", "note": "ignore"},
        {"city": "... subtotal", "country": "US", "population": "123", "area_sqkm": "1", "is_test": "", "note": "ignore"},
        {"city": "", "country": "US", "population": "456", "area_sqkm": "1", "is_test": "", "note": "ignore"},
        {"city": "Testopolis", "country": "US", "population": "777777", "area_sqkm": "77", "is_test": truthy_str(), "note": "ignore"},
    ])

    with open(POP_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["city", "country", "population", "area_sqkm", "is_test", "note"]
        )
        writer.writeheader()
        writer.writerows(rows)


def write_gdp():
    rows = []
    for idx, (canon, aliases) in enumerate(CITIES, start=1):
        gdp = round(40 + idx * 11.7, 1)
        unemp = round(2.5 + (idx * 0.37) % 5.5, 1)
        industry = INDUSTRIES[idx % len(INDUSTRIES)]

        alias = aliases[1] if len(aliases) > 1 else aliases[0]
        rows.append({
            "city": alias,
            "gdp_billion": fmt_float(gdp),
            "major_industry": industry,
            "unemployment_rate": fmt_pct(unemp),
            "is_test": "",
            "source": "main"
        })

        if idx % 5 == 0:
            alt = aliases[-1]
            rows.append({
                "city": alt,
                "gdp_billion": fmt_float(gdp + 3.2),
                "major_industry": industry,
                "unemployment_rate": fmt_pct(max(0.1, unemp - 0.4)),
                "is_test": "",
                "source": "better duplicate"
            })

        if idx % 6 == 0:
            rows.append({
                "city": canon,
                "gdp_billion": maybe_dirty_null(),
                "major_industry": industry,
                "unemployment_rate": maybe_dirty_null(),
                "is_test": "",
                "source": "bad duplicate"
            })

    rows.extend([
        {"city": "# comment row", "gdp_billion": "999.9", "major_industry": "Fake", "unemployment_rate": "1.0%", "is_test": "", "source": "ignore"},
        {"city": "... scratch", "gdp_billion": "123.4", "major_industry": "Fake", "unemployment_rate": "2.0%", "is_test": "", "source": "ignore"},
        {"city": "", "gdp_billion": "55.5", "major_industry": "Fake", "unemployment_rate": "3.0%", "is_test": "", "source": "ignore"},
        {"city": "Sandbox City", "gdp_billion": "88.8", "major_industry": "Fake", "unemployment_rate": "4.0%", "is_test": truthy_str(), "source": "ignore"},
    ])

    with open(GDP_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(
            f,
            fieldnames=["city", "gdp_billion", "major_industry", "unemployment_rate", "is_test", "source"]
        )
        writer.writeheader()
        writer.writerows(rows)


if __name__ == "__main__":
    os.makedirs(PROJECT_DIR, exist_ok=True)
    write_population()
    write_gdp()
    print("Generated population.csv and gdp_data.csv")