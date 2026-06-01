# Task: Compare two supplier quotes and recommend the more cost-effective one

The task files are in `/root/task`.

Procurement handed you two PDF quotes from different suppliers and only asked for a recommendation. To answer correctly, you first need to extract the comparable fields from both PDFs and then compare total cost, not just the visible unit price.

Start by reading:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/quote_parser.py`
- `/root/task/charge_policy.py`

What to deliver:
1. Extract both quotes into structured data.
2. Include shipping in total cost.
3. Recommend the better quote based on full landed cost and mention the shipping difference.

Save all edits under `/root/task`.

## Required Outputs and Schema
Run `run_analysis.sh` so it writes `/root/task/output.json`.
The JSON object must include `quote_a`, `quote_b`, and `comparison`. Each quote object must include extracted item/quantity/price information and `total_cost` including shipping or freight. `comparison` must include `recommended_supplier`, the total-cost basis for the recommendation, and text or fields that mention the shipping/freight difference. The recommendation must be based on total landed cost, not unit price alone.

