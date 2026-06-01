# Customer Revenue Unification

Three upstream feeds need to be aligned:

- `crm_contacts.csv`: canonical-ish customer names, city, revenue band inputs.
- `erp_orders.csv`: many order rows with abbreviated company names.
- `external_ratings.csv`: one row per company, usually uppercased or expanded names.

The current pipeline tries a name match first but falls back to city-level matching for unresolved ERP rows. That fallback causes multi-company fanout in shared cities like Houston and Phoenix.
