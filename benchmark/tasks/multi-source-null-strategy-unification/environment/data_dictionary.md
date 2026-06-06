# Data Dictionary — Multi-Source Product Data

## Supplier A (supplier_a.csv)
- Missing values: **empty string** (shows as NaN when loaded with pandas)
- `stock = 0` means out of stock (valid)

## Supplier B (supplier_b.csv)
- Missing values: **"N/A"**, **"null"**, or **empty string**
- `stock = 0` means out of stock (valid)

## Supplier C (supplier_c.csv)
- Missing values: **-1** (unknown) or **-999** (data error)
- `stock = 0` means out of stock (**valid — do NOT treat as missing**)
- `price = 0` is NOT valid (no free products from this supplier)

## Common Rules
- After standardization, all missing values should be NaN
- `stock = 0` is ALWAYS a valid value across all suppliers
- `price = 0` is valid for suppliers A and B, but NOT for C
