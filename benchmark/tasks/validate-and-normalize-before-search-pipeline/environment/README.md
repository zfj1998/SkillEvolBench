# Environment Plan: E2-LS1-T4

Role: `context_shift`
Gap focus: `Validation is implicit inside a larger natural-language-to-search pipeline.`

Scenario:
The input is a natural-language query such as 'Show me sales in California from last month, sorted by amount descending'. The pipeline must extract parameters, normalize them, validate them, call the API, and summarize the result.

Environment files:
- `pipeline.py`
- `query.txt`
- `mock_api.py`
- `public_tests/test_pipeline.py`

Key design notes:
The environment should require mapping `California -> CA`, deriving the full previous month date range, and preserving descending sort. The user instructions should not explicitly mention validation or parameter extraction.

Public checks:
- The report is non-empty.
- The output format matches the expected summary schema.

Hidden checks:
- The API call uses normalized state code and ISO dates.
- The date range covers the full previous month.
- Results are sorted by amount descending.
- The report includes count, total amount, and average amount.

Process checks:
- The implementation performs parameter extraction before the call.
- Validation happens before the outbound request.
- Trace contains no malformed search requests.
