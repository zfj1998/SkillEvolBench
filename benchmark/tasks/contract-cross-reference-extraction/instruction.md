# Task: Build a contract cross-reference map and detect cycles

The task files are in `/root/task`.

Legal operations wants a machine-readable cross-reference map for the contract in `contract.txt`, including Appendix and Schedule references and any circular reference chains.

The starter has the basic indexing shape, but its reference extraction is still too narrow and its cycle detection is missing.

Start by reading:
- `/root/task/README.md`
- `/root/task/analyzer.py`
- `/root/task/clause_index.py`
- `/root/task/reference_patterns.py`

What to deliver:
1. Extract all document references with source, target, and target type.
2. Detect the circular reference chain in the contract.
3. Avoid false positives from casual uses of the word "section".

Save all edits under `/root/task`.

## Required Outputs and Schema
`analyzer.py` must produce a JSON object when called by the runner or imported by the tests; no separate output file is required for this task.
The object must contain `references` and `cycles`. Each reference is an object with `source`, `target`, and `target_type`, where `target_type` is one of `section`, `appendix`, or `schedule`. The `cycles` array lists circular reference chains, including the cycle involving Section 2.1, Section 3.2(b), and Section 5.1. Avoid duplicate source/target pairs and false positives from ordinary uses of the word section.

Implementation requirement: keep the analyzer structured enough to inspect. Use the existing indexing/extraction helpers (`index_sources`, `extract_reference_candidates`), build an explicit graph of references, and use a real cycle-detection traversal such as DFS with visited/stack state rather than a one-off hardcoded cycle list.
