# Task: E5-LS5-T3

The task files are in `/root/task`.

Review the annual report for internal consistency across summary, body, tables, and conclusion.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.
Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Review internal consistency by comparing summary, table, body, and conclusion claims in the same document context; include both document locations and exact conflicting values.

Implementation guidance: keep the starter pipeline structure, but refine `scope_normalizer.py` and `contradiction_policy.py` so candidate pairs are compared by entity, metric, period, scope, document location, value, and polarity. Use `claim_graph.json` to enumerate pairs and consult `source_cards.md`, `source_url_index.json`, and `evidence_index.json` for provenance. Mark only same-document, same-context inconsistencies as type `internal`, and leave compatible same-document claims unflagged.
