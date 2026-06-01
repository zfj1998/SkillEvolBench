# Fixture Plan: E1-LS3-T6

Role: `composition`
Gap focus: `Composition of refactoring with coverage-driven diagnosis.`

Scenario:
A 200-line analysis function mixes validation, statistics, outlier detection, and report generation. Existing tests only cover the happy path, so the solver must refactor and then use coverage data to discover missing edge cases.

Intended fixture files:
- `analyzer.py`
- `public_tests/test_analyzer.py`
- `.coveragerc`

Key design notes:
The hidden edge cases should include empty lists, single-element input, all-equal values, negative values, and degenerate distributions. The fixture should visibly reward the use of coverage tooling.

Public checks:
- Existing tests still pass after the refactor.
- Coverage reaches at least 90 percent.

Hidden checks:
- Empty input returns a controlled error instead of crashing with ZeroDivisionError.
- All-equal values report zero standard deviation and no outliers.
- Single-value input behaves correctly.

Process checks:
- `analyze_data()` is split into at least four functions or focused units.
- The solver uses `coverage run` or an equivalent coverage tool.
- At least eight new tests are added, including edge cases.
