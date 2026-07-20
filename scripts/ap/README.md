# Agent Platform helpers

## Complete platform-log export

AP CLI `0.1.16` can silently write empty platform-log files because it asks the
server for 1,000 entries while the server accepts at most 500. Export the job
without the stock `--logs` option, then run:

```bash
ap --cluster benchmark-dev job export JOB_ID -o EXPORT_DIR --events
python scripts/ap/export_platform_logs.py \
  JOB_ID EXPORT_DIR --cluster benchmark-dev
```

The exporter requires a terminal AP job, discovers every container, follows
each `next_offset` through its terminal null value with a 500-entry page limit,
and repeats the API reads before accepting the local SHA-256 and byte size. It
writes mode-`0600` logs plus `logs/pagination_manifest.json` atomically under a
mode-`0700` directory. It does not open `artifacts.json` or print log contents,
credentials, or transport metadata.
