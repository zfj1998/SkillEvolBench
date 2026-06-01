# Electronics Extract Notes

The catalog is intentionally messy because it combines supplier feeds and manual merchandising edits.

Important details:
- category values are not perfectly standardized
- zero-width and BOM-like characters occasionally appear in text fields
- inactive rows should not be shipped to reporting
- malformed `price` or `stock_quantity` values should be excluded from the final extract

The output is expected to be a validated Electronics extract rather than a raw SQL dump. In practice the active Electronics slice should be in the high hundreds, not a tiny sample.
