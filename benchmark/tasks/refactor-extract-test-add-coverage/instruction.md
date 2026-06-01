# Refactor the analysis function and use coverage to close the gaps

The analytics project is in `/root/task`. `analyze_data()` is too large and the current tests only cover the happy path. We need the function broken into smaller units and the test suite pushed above 90% line coverage.

Please update the code and tests in place under `/root/task`:
- refactor `analyze_data()` into smaller focused units
- split the implementation into at least four focused helper functions so validation, statistics, outlier detection, and report generation can be tested independently
- keep the current behavior working for the covered paths
- use coverage-driven checks after the refactor
- add at least eight new tests for the missing edge cases instead of only rewriting the implementation

Expected `analyze_data(values)` result schema:
- Returns a dictionary with keys `count`, `mean`, `median`, `stddev`, `q1`, `q3`, `outliers`, `spread`, `negative_ratio`, `report`, `zero_count`, and `error`.
- Numeric fields should be numbers; `outliers` should be a list; `report` should be a string classification.
- Empty input should return a controlled report with `count == 0`, `report == "empty_input"`, and an explanatory `error` instead of raising `ZeroDivisionError`.
- Single-element and all-equal inputs should report `stddev == 0` and no outliers.

Start here:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/public_tests/test_analyzer.py`
- `/root/task/notebooks/exploration.txt`
- `/root/task/docs/statistics-glossary.md`

Keep all edits inside `/root/task`. Do not replace the project with a stub.
