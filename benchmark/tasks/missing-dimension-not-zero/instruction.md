# Task: Compare platforms without turning missing data into zeros

The task files are in `/root/task`.

Build a comparison matrix and mark unavailable dimensions honestly.
The starter treats missing fields as zero-like values and biases the result.

Save the matrix to `/root/task/output/comparison_matrix.json`.

Grounding artifacts are provided in `source_url_index.json`, `evidence_index.json`, `references.bib`, `schemas/output_schema.json`, `provenance.py`, and `source_quality.py`. Use these files to keep the answer source-grounded rather than relying on synthetic article bodies.

The missing-value behavior is centralized in `/root/task/missingness_policy.py`; fix that policy so unavailable dimensions remain explicitly unavailable instead of becoming numeric zeroes in the comparison matrix.
