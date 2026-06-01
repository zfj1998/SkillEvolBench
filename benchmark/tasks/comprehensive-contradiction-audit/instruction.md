# Task: E5-LS5-T6

The task files are in `/root/task`.

Conduct a comprehensive consistency audit across all documents and classify each issue.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.
Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Classify explicit, implicit_timeline, implicit_causal, implicit_definition, and internal contradictions; do not flag pairs that differ only by timeframe or scope.

Implementation guidance: keep the starter pipeline structure, but refine `scope_normalizer.py` and `contradiction_policy.py` so the classifier uses entity, metric, period, and scope before deciding that two claims conflict. The audit should use `claim_graph.json` to enumerate candidate pairs and consult the grounded files (`source_cards.md`, `source_url_index.json`, and `evidence_index.json`) for provenance rather than treating pair IDs as answers. The output must preserve evidence quotes for both sides of each flagged contradiction and distinguish the required contradiction types: explicit numeric/date/polarity conflicts, timeline conflicts, causal/budget conflicts, definition/market-position conflicts, and internal same-document conflicts.
