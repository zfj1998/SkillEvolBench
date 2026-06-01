# Environment: E2-LS3-T3

Scenario:
An order export runs while new rows are inserted. Offset pagination now drifts unless the client switches to a consistent cursor flow or explicitly reacts to the changing total.

Starter files:
- `solution.py`: export entrypoint
- `scan_strategy.py`: decides how pages are requested
- `consistency_guard.py`: decides whether a total change should trigger recovery
- `order_buffer.py`: merge helpers for collected rows
- `mock_api.py`: simulated changing dataset with offset and cursor modes
- `docs/order-feed-consistency.md`: migration notes from the orders platform team

Key design notes:
- the starter still defaults to the old offset scan
- it notices total changes, but only treats shrink events as consistency issues
- new rows inserted at the front of the dataset will be missed unless the client adapts
