# Task: E5-LS5-T5

The task files are in `/root/task`.

Identify genuine contradictions without over-flagging different years, scopes, or time scales.

Use the grounded source cards, source URL index, evidence index, and claim graph, then write `/root/task/output/consistency_audit.json`. Keep provenance explicit and do not rely on synthetic article bodies.

Output contract: write `/root/task/output/consistency_audit.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: refine `scope_normalizer.py` and `contradiction_policy.py` so the classifier compares claim entity, metric, period, scope, value, and polarity. Mark same-context incompatible market-size values and direct affirm/deny expansion claims as explicit contradictions. Do not flag pairs that differ only by year, geographic scope, or short-term versus long-term time scale. Preserve both evidence quotes and provenance for every checked pair.
