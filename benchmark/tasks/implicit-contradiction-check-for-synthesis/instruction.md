# Task: E5-LS5-T4

The task files are in `/root/task`.

Prepare a synthesis-ready consistency audit before writing the research summary.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.
Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Before synthesis, audit source consistency and classify contradictions such as implicit timeline or causal conflicts while avoiding unsupported merges.

Modify `contradiction_policy.py` and `scope_normalizer.py` as needed to implement the consistency checks.
