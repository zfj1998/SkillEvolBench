# Data Dictionary — employee_data.csv

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
