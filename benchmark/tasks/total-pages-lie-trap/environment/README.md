# Environment: E2-LS3-T5

Scenario:
The report API exposes `total_pages`, but that metadata is not stable. The starter still precomputes a fixed fetch plan from page 1 and never refreshes it.

Starter files:
- `solution.py`: report collector entrypoint
- `page_plan.py`: builds the page fetch plan
- `report_cache.py`: stores page 1 metadata
- `report_audit.py`: weak success thresholds
- `mock_api.py`: report API with changing `total_pages`
- `docs/reporting-api-notes.md`: notes from the reporting platform team

Key design notes:
- the starter makes enough calls to look plausible
- it still trusts the first page too much and stops at 5 pages
- the correct solution must keep checking fresh metadata or `has_more`
