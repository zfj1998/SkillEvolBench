This fixture simulates a procurement quote comparison workflow.

Relevant files:
- `supplier_a_quote.pdf`
- `supplier_b_quote.pdf`
- `quote_parser.py`: common field extraction
- `charge_policy.py`: derives full landed cost from the parsed quote
- `analyzer.py`: compares the two suppliers

Starter limitation:
- supplier B's freight note is treated as non-billable metadata instead of part of total cost
