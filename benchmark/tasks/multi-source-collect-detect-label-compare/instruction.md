# Task: Collect, label, and compare evidence from multiple source types

The task files are in `/root/task`.

Label source provenance correctly, separate vendor material from independent evidence, and prepare a board-ready comparison.

Save the result to `/root/task/output/board_report.json`.
Output contract: write `/root/task/output/board_report.json`. Follow the field structure documented by the starter pipeline and `schemas/output_schema.json` when the output is JSON.

Required behavior: Label vendor versus independent evidence, keep provenance/source IDs visible in the labels, and base the decision on that split rather than treating all sources equally.

Use `source_manifest.json` as the source of truth for provenance. Sources with `source_type` of `vendor_doc` or `vendor_community` must be labeled `vendor`; sources with `source_type` of `independent_review` must be labeled `independent`; every source ID from the manifest should appear exactly once in `labels`. The board decision should be derived from the labeled split: vendor material can support factual product claims, but independent reviews should carry distinct weight for usability and tradeoff judgments. The decision basis should explicitly describe the vendor/independent split and should not be a fixed sentence unrelated to the loaded evidence.
