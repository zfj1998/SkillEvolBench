# Task: Build a multi-dimension comparison table

The task files are in `/root/task`.

Compare the two CRM platforms across all relevant dimensions and support each dimension with source evidence.
The starter matrix under-covers dimensions and cites too sparsely.

Save the comparison data to `/root/task/output/comparison.json`.

Grounding artifacts are provided in `source_url_index.json`, `evidence_index.json`, `references.bib`, `schemas/output_schema.json`, `provenance.py`, and `source_quality.py`. Use these files to keep the answer source-grounded rather than relying on synthetic article bodies.

The comparison must retain at least the six relevant dimensions in `dimension_registry.py` and carry those dimensions through to `/root/task/output/comparison.json`, with source evidence for each dimension. The final output must conform to `schemas/output_schema.json`.

Each row in `output/comparison.json` must compare both CRM products, not only list a dimension and citations. For every covered dimension include:
- `dimension`: the comparison dimension name.
- `crm_a`: a concise, evidence-grounded summary for Salesforce.
- `crm_b`: a concise, evidence-grounded summary for HubSpot.
- `winner`: one of `salesforce`, `hubspot`, `tie`, or `insufficient_evidence`.
- `sources`: source IDs or citation keys supporting the row.

At least six rows must populate `crm_a`, `crm_b`, and `winner` so the table is a true side-by-side comparison with a defensible choice per dimension.
