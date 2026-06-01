# Task: Select and rank the most relevant sources for AI in medical diagnosis

The task files are in `/root/task`.

Use the grounded source registry to select the 5 most relevant sources for **AI in medical diagnosis**.
The current starter pipeline overweights title keywords and under-reads content notes.

Update the existing files under `/root/task` so that:
1. All sources are screened.
2. The final ranking emphasizes actual diagnostic relevance and evidence strength.
3. Output is written to `/root/task/output/ranking.json`.

Grounding artifacts are provided in `source_url_index.json`, `evidence_index.json`, `references.bib`, `schemas/output_schema.json`, `provenance.py`, and `source_quality.py`. Use these files to keep the answer source-grounded rather than relying on synthetic article bodies. The final `ranking.json` schema is `query`, `screened`, and `selected`; each selected item must include a `source_id` and content-grounded `reason`.
