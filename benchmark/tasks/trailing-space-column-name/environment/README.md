# ERP Export Notes

- Source file: `sales.csv`
- The file came from an ERP export and was handed off without any schema normalization.
- Analysts expect canonical fields: `id`, `name`, `amount`, `date`.
- The finance team uses `amount` for both grand totals and per-name summaries.
- Do not hardcode positional columns. The export order changes between regions.
