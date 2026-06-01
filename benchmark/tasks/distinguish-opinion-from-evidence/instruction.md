# Task: Classify sources as evidence-based or opinion-based

The task files are in `/root/task`.

Classify each source and prioritize the evidence-based ones.
The starter policy treats study-like wording as evidence too easily and misses pseudo-evidence.

Save the final structured output to `/root/task/output/classification.json`.
Output contract: write `/root/task/output/classification.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Classify every source as evidence or opinion, include a repeatable classification standard, and prioritize evidence-based sources in selected_priority.
