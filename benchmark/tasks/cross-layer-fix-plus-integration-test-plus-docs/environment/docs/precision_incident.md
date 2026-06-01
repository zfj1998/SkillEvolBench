# Precision Incident

- Finance observed some totals rendered as floating-point artifacts.
- The API docs already describe `total_amount` as decimal-safe text, but the implementation path has drifted.
- Any fix here needs code, regression coverage, and docs to stay aligned.
