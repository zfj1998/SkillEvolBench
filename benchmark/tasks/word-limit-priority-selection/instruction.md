# Task: E5-LS4-T2-word-limit-priority-selection

The task files are in `/root/task`.

Summarize in no more than 500 words, prioritizing the most important findings over background.

The starter summarizer preserves document order too strongly. Refine the policy and summarizer so the output respects the constraints and source evidence.
Output contract: write `/root/task/output/summary.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: The summary should prioritize high-value findings and recommendations over background, avoid simple leading-section truncation, and include selected_sections plus word_count.
