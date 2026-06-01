# Invoice Extraction Fixture

This fixture simulates a small ERP ingestion service that extracts supplier invoices from PDFs.

Core inputs:
- `invoice_main.pdf`: two-page invoice, 20 line items, subtotal `1250.00`
- `invoice_boundary.pdf`: threshold edge case, subtotal `1000.00`

Code structure:
- `invoice_reader.py`: low-level PDF text loading and row grouping
- `pricing_policy.py`: discount threshold and tax-base policy
- `analyzer.py`: orchestration and JSON shaping

Expected output shape:
- top-level `{"invoices": [...]}`
- each invoice includes `line_items`, `discount`, `tax`, and `total`

Known starter gaps:
- line-item currency is not reliably preserved in the final JSON
- the "Orders over $1,000" rule is treated as `>=`
- tax base is still calculated from the pre-discount subtotal
