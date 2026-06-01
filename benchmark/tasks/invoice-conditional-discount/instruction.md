# Task: Extract a multi-page supplier invoice into JSON

The task files are in `/root/task`.

Finance needs a structured JSON export for two invoice PDFs:
- `invoice_main.pdf`: 20 line items across two pages, mixed currencies, conditional discount, two taxes
- `invoice_boundary.pdf`: subtotal is exactly the discount threshold edge case

The current extractor is close, but it still has contract bugs in how it preserves line-item metadata and applies pricing rules.

Start by reading:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/invoice_reader.py`
- `/root/task/pricing_policy.py`

What to deliver:
1. Extract all invoice fields into JSON.
2. Keep page-two line items continuous with page one.
3. Preserve per-line currency.
4. Apply the conditional discount and post-discount tax bases correctly.

Save all edits under `/root/task`. Do not replace the task with a stub or hardcoded output.

## Required Outputs and Schema
Run `run_analysis.sh` so it writes `/root/task/output.json`. The JSON object must contain `invoices`, an array with both `INV-1001` and `INV-1002`.
Each invoice object must include `invoice_number`, `line_items`, `subtotal`, `discount`, `tax`, and `total`. Each `line_items` entry must include `index`, `description`, numeric amount fields, and `currency` (`USD`, `EUR`, or `JPY`). `discount` must include `applied`, `amount`, and the condition used. `tax.state.base` must use the discounted subtotal. Do not include page headers, footers, or thank-you text as line items.
