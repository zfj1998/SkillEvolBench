# Task: Compare 2023 And 2024 Product Sales

The task files are in `/root/task`.

The business request is to compare 2023 and 2024 product sales and identify products with strong growth or notable decline. The two yearly exports are not directly comparable as-is, so inspect the product keys before doing the comparison.

What to do:
1. Inspect `sales_2023.csv` and `sales_2024.csv`.
2. Update the comparison pipeline so matching products align before growth calculations.
3. Save the comparison result to `output.json`.

Make the fix in place under `/root/task`. Do not replace the project with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `coverage_ratio` (number): fraction of prior-year products aligned to the comparison set.
- `growth_products` (array of strings): product names classified as growth.
- `decline_products` (array of strings): product names classified as decline.
- `records` (array of objects): each object includes the normalized product key, prior/current sales values, `growth_rate`, and `trend` (`growth`, `decline`, or `flat`).

Design contract: normalize product names by trimming whitespace, removing punctuation noise, lowering case, and applying the aliases supplied in the starter files. Deduplicate repeated snapshots before comparison. Compute growth as `(current - prior) / prior`; classify `growth` when growth is greater than 20%, `decline` when less than -10%, otherwise `flat`.

