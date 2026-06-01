# Year-over-Year Sales Comparison

The two yearly exports were produced by different reporting jobs.

- `sales_2023.csv` uses older product labels and contains duplicate export snapshots.
- `sales_2024.csv` uses a newer labeling style, and several products have punctuation or spacing differences from the 2023 labels.

The current comparison logic assumes exact product labels and therefore misclassifies aligned products as new or missing.
