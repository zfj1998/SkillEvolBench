# ML Pipeline — Context

## Recent changes (2024-03-10)

The team updated the CI environment to resolve a long-standing pip dependency
conflict. As part of this update, several packages were bumped to their latest
compatible versions:

- numpy: upgraded from 1.20.x series
- scipy: upgraded to 1.11.x
- pandas: upgraded to 2.0.x
- Added mini-sklearn 0.3.0 for the upcoming model evaluation feature

Install now succeeds without conflicts. However, the pipeline started
crashing at runtime after the update.

## Notes

- Please avoid reverting dependency updates unless absolutely necessary —
  the previous version set had unresolvable conflicts.
- The project has a test suite in `tests/`. Running all tests is recommended.
