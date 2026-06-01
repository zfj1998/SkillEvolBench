# Task: Merge Population And GDP By City

The task files are in `/root/task`.

Two city datasets need to be merged for a metro market briefing. The city labels are not consistent across sources, so exact string matching is currently dropping valid matches.

What to do:
1. Inspect the schemas and the city values in `population.csv` and `gdp_data.csv`.
2. Update the merge pipeline so city name variants can still align to the same city.
3. Save a clean merged result to `output.json`, and report unmatched cities.

Make the fix in place under `/root/task`. Do not replace the project with a stub.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of matched city records.
- `matched_count` (integer): same logical matched-city count used by the merge audit.
- `records` (array of objects): merged city rows including `canonical_city`, population fields, GDP fields such as `gdp_billion`, and source audit columns.
- `unmatched` (object): contains `population_without_gdp` and `gdp_without_population`, each an array of unmatched city identifiers.

Design contract: normalize city keys by trimming whitespace including non-breaking spaces, removing punctuation, lowering case, and resolving variants such as NYC/New York, LA/Los Angeles, and Saint Louis/St Louis. Resolve duplicate variants with an explicit source-priority rule rather than creating fanout: prefer rows with valid numeric values, and when a GDP duplicate source is marked `better duplicate`, prefer it over the `main` candidate for the same canonical city.
