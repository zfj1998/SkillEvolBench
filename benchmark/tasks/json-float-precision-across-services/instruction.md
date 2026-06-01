# Fix the false mismatches between the two services

The reconciliation setup lives in `/root/task`. Service A recalculates order totals and sends them over JSON, and Service B compares those values against the database. Some orders now come back as `MISMATCH` even though finance says nothing changed.

Please fix the real cross-service issue in place:
- the known false mismatches should become matches
- real amount changes must still stay detectable
- keep the service boundary realistic instead of hardcoding special cases

Expected data contracts:
- Service A sends JSON order payloads with `id`, `item`, `quantity`, `unit_price`, and `calculated_total`.
- Monetary fields crossing the JSON boundary must preserve cents-level precision; use a decimal-safe representation or equivalent precision-preserving strategy rather than binary-float artifacts.
- Service B reconciliation results are dictionaries containing `id` and `status`; mismatch results also include `api_total` and `db_total`.
- `status` should be `"MATCH"` for cent-equivalent totals and `"MISMATCH"` for real amount changes.

Start here:
- `/root/task/service_a/calculator.py`
- `/root/task/service_a/api.py`
- `/root/task/service_b/reconciler.py`
- `/root/task/service_b/api.py`
- `/root/task/shared/models.py`

Save your edits under `/root/task`. Keep the current two-service layout.
