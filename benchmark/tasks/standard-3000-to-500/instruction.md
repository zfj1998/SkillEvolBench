# Task: E5-LS4-T1-standard-3000-to-500

The task files are in `/root/task`.

Summarize the dossier in no more than 500 words while preserving the core findings and recommendations.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: The summary should preserve core findings and recommendations, compress background/appendix material, and include selected_sections plus word_count.

Prioritize the dossier's high-value evidence sections over introductory order. The final summary should include the core source/authority concepts `nature`, `jama`, `fda`, `who`, and `monitoring`; select the sections `finding_skin`, `finding_retina`, `governance_fda`, `ethics_who`, and `recommendation`; and omit low-value phrases such as `appendix tables` and `background history`. The implementation should use the provided policy modules to rank content and write structured `summary.json` rather than copying a fixed opening slice.
