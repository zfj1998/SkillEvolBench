# Fix the false-positive change detection in the ETL pipeline

The ETL project is in `/root/task`. Ops is complaining that the pipeline now marks almost every record as changed, even when the amount has not actually moved. The noisy output is breaking reconciliation review.

Please debug the existing pipeline in place and fix the real root cause. Keep the rest of the flow working:
- unchanged records should stop being flagged
- real amount changes still need to be detected
- do not paper over the issue by disabling change detection

Expected pipeline report schema:
- `run_pipeline_report(...)` returns a dictionary with `total`, `changed_count`, `unchanged_count`, `changed_records`, `unchanged_records`, and `change_summary`.
- `total` is the number of processed records.
- `changed_count` and `unchanged_count` are counts that add up to `total`.
- `changed_records` and `unchanged_records` are lists of the corresponding per-record dictionaries.
- `change_summary` is a list of human-readable summaries generated for each record.

Start here:
- `/root/task/pipeline.py`
- `/root/task/extractor.py`
- `/root/task/validator.py`
- `/root/task/transformer.py`
- `/root/task/enricher.py`
- `/root/task/loader.py`

Make your edits under `/root/task`. Keep the project runnable from there and do not replace the pipeline with a stub.

Deliverable note: no standalone output file is required. The verifier checks the dictionary returned by `run_pipeline_report(...)`; keep that return schema exactly as documented while fixing the existing pipeline code in place.
