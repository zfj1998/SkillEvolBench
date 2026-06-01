# Environment: E2-LS3-T6

Scenario:
Two regional APIs must be paged independently, then merged into one export. The US feed has a transient 503 on page 3. Some orders are shared across both feeds and should collapse to one final row.

Starter files:
- `solution.py`: top-level export entrypoint
- `regional_sync.py`: region-specific pagination and retry logic
- `retry_policy.py`: transient retry rules
- `merge_index.py`: cross-region merge helpers
- `merge_audit.py`: weak final export checks
- `mock_api.py`: dual-region backend with retry trace recording
- `docs/regional-sync-notes.md`: operational notes for the export pipeline

Key design notes:
- the starter does retry and does read both feeds, so it looks credible
- the merge layer still scopes identity by source region, so shared orders leak through as duplicates
- the correct solution should keep the retry behavior and fix the merge boundary
