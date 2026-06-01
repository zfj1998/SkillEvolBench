# Task: E5-LS5-T2

The task files are in `/root/task`.

Analyze the notes for inconsistencies that require timeline, causality, or definition reasoning.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.
Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Look beyond direct negation: detect timeline, causal, and definition inconsistencies and provide the reasoning chain for each contradiction.

Implementation guidance: keep the starter pipeline structure, but refine `scope_normalizer.py` and `contradiction_policy.py` so classification is derived from claim fields and grounded evidence rather than pair IDs. Use `claim_graph.json` to enumerate pairs and consult `source_cards.md`, `source_url_index.json`, and `evidence_index.json` for provenance. Detect a timeline contradiction when a specific-year growth claim conflicts with a continuous decline through that year, a causal/budget contradiction when costs decrease while before/after budgets are unchanged, and a definition contradiction when a claimed market leader has only a small market share. Do not flag compatible pairs that discuss different non-conflicting metrics.
