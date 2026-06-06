from __future__ import annotations

import csv
import random
import unicodedata
from pathlib import Path

TOTAL_ROWS = 2000
AGE_EXCLUDED = 137
SALARY_ZERO = 73
TEMP_EXCLUDED = 111

DEPARTMENTS = ["Engineering", "Marketing", "Sales", "HR", "Operations"]
NAMES = ["Alice", "Bob", "Carol", "Dave", "Eva", "Frank", "Grace", "Heidi"]

ZERO_WIDTHS = ["\u200b", "\u200c", "\u200d", "\ufeff"]
MINUS_VARIANTS = ["-", "−"]
QUOTE_PAIRS = [('"', '"'), ("'", "'")]

random.seed(1337)


def zw_wrap(text: str) -> str:
    if random.random() < 0.22:
        return random.choice(ZERO_WIDTHS) + text
    if random.random() < 0.22:
        return text + random.choice(ZERO_WIDTHS)
    if random.random() < 0.08:
        return random.choice(ZERO_WIDTHS) + text + random.choice(ZERO_WIDTHS)
    return text


def maybe_quote(text: str) -> str:
    if random.random() < 0.18:
        lq, rq = random.choice(QUOTE_PAIRS)
        return f"{lq}{text}{rq}"
    return text


def maybe_pad(text: str) -> str:
    left = " " * random.randint(0, 2)
    right = " " * random.randint(0, 2)
    return f"{left}{text}{right}"


def normalize_for_fixture_noise(text: str) -> str:
    return maybe_pad(maybe_quote(zw_wrap(text)))


def format_age(value: int | None) -> str:
    if value is None:
        forms = [
            "-1",
            " -1 ",
            "−1",
            '"-1"',
            "'-1'",
            "N/A",
            "na",
            "Null",
            " NONE ",
        ]
        return normalize_for_fixture_noise(random.choice(forms))

    forms = [
        str(value),
        f"{value}.0",
        f'"{value}"',
        f" {value} ",
    ]
    return normalize_for_fixture_noise(random.choice(forms))


def format_salary(value: int) -> str:
    if value == 0:
        forms = [
            "0",
            "0.0",
            '"0"',
            " 0 ",
            "0_0".replace("_", ""),  # still "00" -> parses to 0 if handled numerically
        ]
        return normalize_for_fixture_noise(random.choice(forms))

    forms = [
        str(value),
        f"{value:,}",
        f"{value:_}",
        f"{value}.0",
        f'"{value:,}"',
    ]
    return normalize_for_fixture_noise(random.choice(forms))


def format_temp(value: float | None) -> str:
    if value is None:
        forms = [
            "-999",
            "-999.0",
            "−999",
            '"-999"',
            "sensor_fault",
            "N/A",
            "null",
            " none ",
        ]
        return normalize_for_fixture_noise(random.choice(forms))

    dot = f"{value:.1f}"
    comma = dot.replace(".", ",")
    forms = [
        dot,
        comma,
        f'"{dot}"',
        f" {dot} ",
    ]
    return normalize_for_fixture_noise(random.choice(forms))


def noisy_header(base: str) -> str:
    variants = {
        "emp_id": "\ufeffemp_id",
        "name": " name ",
        "department": "depart\u200bment",
        "age": "Age",
        "salary": " salary ",
        "site_temperature": "site\u200b_temperature",
    }
    return variants[base]


def main() -> None:
    project_dir = Path(__file__).resolve().parent
    csv_path = project_dir / "employee_data.csv"
    dict_path = project_dir / "data_dictionary.md"

    rows = []

    age_missing_ids = set(random.sample(range(1, TOTAL_ROWS + 1), AGE_EXCLUDED))
    remaining = [i for i in range(1, TOTAL_ROWS + 1) if i not in age_missing_ids]
    salary_zero_ids = set(random.sample(remaining, SALARY_ZERO))
    temp_missing_ids = set(random.sample(range(1, TOTAL_ROWS + 1), TEMP_EXCLUDED))

    for emp_id in range(1, TOTAL_ROWS + 1):
        name = f"{random.choice(NAMES)}_{emp_id:04d}"
        dept = random.choice(DEPARTMENTS)

        if emp_id in age_missing_ids:
            age_cell = format_age(None)
        else:
            age_val = random.randint(21, 64)
            age_cell = format_age(age_val)

        if emp_id in salary_zero_ids:
            salary_val = 0
        else:
            salary_val = random.randint(42000, 165000)
        salary_cell = format_salary(salary_val)

        if emp_id in temp_missing_ids:
            temp_cell = format_temp(None)
        else:
            temp_val = round(random.uniform(17.0, 29.5), 1)
            temp_cell = format_temp(temp_val)

        rows.append(
            [
                str(emp_id),
                name,
                dept,
                age_cell,
                salary_cell,
                temp_cell,
            ]
        )

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            [
                noisy_header("emp_id"),
                noisy_header("name"),
                noisy_header("department"),
                noisy_header("age"),
                noisy_header("salary"),
                noisy_header("site_temperature"),
            ]
        )
        writer.writerows(rows)

    dict_text = """# Data Dictionary — employee_data.csv

This file defines the semantics for employee statistics.

## Header normalization
Before matching column names, normalize headers by:
- Unicode NFKC normalization
- trimming surrounding whitespace
- removing zero-width / BOM-like format characters
- lowercasing
- collapsing internal whitespace runs

Expected normalized columns:
- emp_id
- name
- department
- age
- salary
- site_temperature

## Column rules

| Column | Type | Special Values / Notes |
|--------|------|------------------------|
| emp_id | int | Unique identifier |
| name | string | Employee name |
| department | string | One of: Engineering, Marketing, Sales, HR, Operations |
| age | int | Missing age must be excluded. Documented missing forms include: `-1`, `−1`, `N/A`, `NA`, `NULL`, `NONE` |
| salary | int | `0` means unpaid volunteer; this is a VALID value and must NOT be excluded |
| site_temperature | float | Missing temperature must be excluded. Documented missing forms include: `-999`, `-999.0`, `−999`, `sensor_fault`, `N/A`, `NULL`, `NONE` |

## Parsing notes

- Cells may contain surrounding whitespace, quotes, zero-width characters, and Unicode minus signs.
- Salary may include thousands separators such as commas or underscores.
- Temperature may use either `.` or `,` as decimal separator.
- Age values like `34.0` are valid only when exactly integral.
- Salary values like `50000.0` are valid only when exactly integral.
- Do not assume one column's sentinel rules apply to another column.
"""
    dict_path.write_text(unicodedata.normalize("NFKC", dict_text), encoding="utf-8")

    print("Generated employee_data.csv and data_dictionary.md")


if __name__ == "__main__":
    main()