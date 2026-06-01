# Reading workflow for E5-LS5-T4

1. Load the claim graph and source manifest.
2. Use `source_url_index.json` and `evidence_index.json` to keep domain grounding explicit.
3. Classify candidate pairs by matching entity, metric, period, and scope before labeling a contradiction.
4. Separate direct contradictions from implicit timeline, internal, definition, and false-positive cases.
5. Do not claim the analyst examples are direct quotes from the linked public sources.
