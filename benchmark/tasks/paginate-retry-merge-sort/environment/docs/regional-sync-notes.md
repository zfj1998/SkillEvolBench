Regional export notes:

- `orders_us` and `orders_eu` should both be paged to completion
- a transient `503` on `orders_us` page 3 is expected and should be retried
- some orders exist in both regional feeds as the same business order
- final deduplication must use the business order id, not the source region
- each regional feed keeps `created_at` in its original local timezone offset
- the merged export should be sorted chronologically, not by raw timestamp string
