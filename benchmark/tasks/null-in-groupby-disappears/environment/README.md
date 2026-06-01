# Regional Sales Rollup

`regional_sales.csv` is assembled from several operational feeds.

Known issues in the raw export:

- region labels use multiple aliases (`E`, `East`, `western`, full-width text, etc.)
- some rows have unresolved or blank region values
- the business still expects unresolved rows to remain visible in the final rollup instead of silently disappearing

The intended workflow is:

1. normalize the region key
2. aggregate sales by canonical region
3. keep unresolved rows in an explicit bucket
4. reconcile the grouped total back to the source total
