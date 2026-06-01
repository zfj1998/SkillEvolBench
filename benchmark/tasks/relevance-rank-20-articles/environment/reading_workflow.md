# Reading workflow for E5-LS1-T1

1. Load `source_manifest.json` and `source_url_index.json`.
2. Use `evidence_index.json` to map claims or dimensions to source IDs.
3. Apply the task-specific pipeline/policy files before writing output.
4. Write the normalized ranking payload expected by `schemas/output_schema.json`.
5. Do not invent citations or rely on title keywords alone.
