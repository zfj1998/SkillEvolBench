The reporting API can grow during retrieval.

Known behavior:
- the first page includes `total_pages`, but later responses may increase it
- `has_more` reflects the latest state of the dataset
- clients should not precompute a fixed page range from page 1 metadata
