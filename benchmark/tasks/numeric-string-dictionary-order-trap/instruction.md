# Task: Fix The Product Catalog Ordering

The files for this task are under `/root/task`.

The catalog export in `/root/task/products.csv` should be sorted by `product_id` ascending, but the
current implementation in `/root/task/process_products.py` is still treating the identifier like a
plain string key.

What you should do:
1. Fix the ordering logic so product ids are sorted naturally.
2. Preserve all rows and save the ordered catalog to `/root/task/output.json`.
3. Make sure legacy ids such as `007` still land in the correct numeric position.

Please update the code in `/root/task` in place.

## Required Output Schema
Write `/root/task/output.json` as a JSON object with:
- `row_count` (integer): number of products retained.
- `records` (array of objects): all product records in natural numeric product-id order.

Design contract: implement numeric ID normalization in `id_normalizer.py` using integer conversion, so `9` sorts before `10` and zero-padded legacy IDs such as `007` sort by their numeric value. `catalog_sort.py` must create and sort by a `product_id_normalized` column instead of sorting the raw string ID.

