# Environment: E2-LS3-T2

Scenario:
An ingestion worker consumes an event-stream API that uses opaque cursors. The service controls page size, and some pages may repeat a boundary event after compaction.

Starter files:
- `solution.py`: current collector entrypoint
- `cursor_contract.py`: request-shape helpers for the event API
- `event_buffer.py`: merge helpers for fetched events
- `stream_audit.py`: weak completeness checks
- `mock_api.py`: simulated cursor-based backend with trace recording
- `docs/event-stream-api.md`: notes from the event platform team

Key design notes:
- the starter follows the cursor chain, but still leaks a fixed `limit` hint from an older offset client
- the starter also trusts the stream not to repeat ids across page boundaries
- the correct solution should treat cursors as opaque and return 80 unique events
