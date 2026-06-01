# Task: E5-LS5-T1

The task files are in `/root/task`.

Compare the two market memos and identify contradictions with evidence.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.
Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Compare candidate pairs in the same entity/metric/period/scope, detect numeric, date, and direct-polarity conflicts, and include both evidence quotes.

Implementation guidance: keep the starter pipeline structure, but refine `scope_normalizer.py` and `contradiction_policy.py` so candidate pairs are classified by comparing claim fields rather than by pair ID. Use `claim_graph.json` to enumerate pairs, use the grounded files (`source_cards.md`, `source_url_index.json`, and `evidence_index.json`) for provenance, and only mark a contradiction when two claims share the same relevant context and have incompatible numeric values, dates, or direct affirm/deny polarity. Leave compatible agreement pairs as not_contradiction.
