This fixture simulates an annual-report extraction utility.

Relevant files:
- `annual_report.pdf`
- `revenue_sources.py`: evidence extraction from summary and financial pages
- `conflict_policy.py`: how multiple values are reconciled for output
- `analyzer.py`: orchestration layer

Starter limitation:
- conflicting evidence is still collapsed into one synthetic "corrected" revenue value
