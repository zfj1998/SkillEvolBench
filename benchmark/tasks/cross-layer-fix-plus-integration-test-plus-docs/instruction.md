# Fix the order precision issue, then lock it down with tests and docs

The order API project is in `/root/task`. We have a known precision issue with `total_amount` for some orders, and this needs a complete fix: code, regression coverage, and API docs all need to agree afterward.

Please update the existing project in place:
- fix the precision bug at the model / query / service layer
- add integration-style regression coverage for it in a new file such as `/root/task/public_tests/test_order_precision_integration.py`
- make sure the OpenAPI docs match the real response shape

Start here:
- `/root/task/api/routes.py`
- `/root/task/services/order_service.py`
- `/root/task/models/order.py`
- `/root/task/database/queries.py`
- `/root/task/public_tests/test_orders.py`
- `/root/task/docs/openapi.yaml`
- `/root/task/docs/README.md`

Save your edits under `/root/task`. Keep the existing project structure and add to it instead of replacing it.
