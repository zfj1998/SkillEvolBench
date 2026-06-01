# Task: E5-LS4-T4-implicit-ceo-constraint

The task files are in `/root/task`.

Prepare the report for the CEO's review; infer the executive constraints from the audience.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Infer CEO-facing constraints: concise executive style, key numbers/risks, next steps, and no low-level technical detail; include selected_sections and word_count. For this instance the overall synthesis must stay within a 500-word executive limit, include the required business terms surfaced by the policy data such as `pilot`, and exclude low-level implementation terms that the CEO audience does not need.
