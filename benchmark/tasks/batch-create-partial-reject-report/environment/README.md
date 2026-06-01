# Environment Plan: E2-LS1-T3

Role: `variant`
Gap focus: `Gap 2: batch partial success instead of all-or-nothing handling.`

Scenario:
An HR import contains ten employee rows. Exactly four should be created successfully, while the other six fail for missing fields, invalid format, duplicates, or empty-string values.

Environment files:
- `batch_import.py`
- `employees.json`
- `mock_api/app.py`
- `public_tests/test_batch_import.py`

Key design notes:
One duplicate should only become invalid because an earlier record succeeded, so ordering matters. The expected output schema is `success`, `failures`, and `summary` with explicit counts.

Public checks:
- Exactly four create calls succeed.
- The response contains a `failures` collection.

Hidden checks:
- Each failed entry includes the original index plus field and reason.
- Duplicate detection cites the already-created record.
- Empty-string values are distinguished from missing fields.
- Summary counts are exactly total=10, succeeded=4, failed=6.
- Processing order is preserved.

Process checks:
- Invalid rows do not block valid rows.
- The output contains `success`, `failures`, and `summary` sections.
- Order-dependent duplicate logic is correct.
