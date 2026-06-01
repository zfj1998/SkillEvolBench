Tiered offer-processing workflow.

Relevant pieces:
- `users.json` lists the batch to process.
- `mock_api.get_user()` returns both the current `status` and a legacy `billing_tier`.
- `offer_router.py` decides which downstream endpoint to use.
- `offer_formatter.py` shapes the final saved rows.

Expected behavior:
- evaluate each user independently
- premium users go to `/premium/offers`
- standard users go to `/standard/offers`
- save all results to `offers_output.json`
