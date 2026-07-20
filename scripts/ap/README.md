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

## Read-only exported-evidence safety scan

After exporting all environment jobs and the group post-process job, scan the
complete group tree before treating it as durable evidence:

```bash
python scripts/ap/scan_export_safety.py /path/to/exported/group
```

The command recursively scans regular-file content, every filename, and
symlink target text. It flags exact values from a fixed allowlist of sensitive
environment variables, private-key headers, signed-URL query keys,
`sevb-no-auth-*` sentinels, and conservative credential assignments. It also
fails closed on unreadable objects, unsupported filesystem objects, and
symlinks escaping the export root. Symlinks are never followed and the scanner
never writes beneath the scanned tree.

`artifacts.json` content is skipped by default because AP uses it for signed
transport URLs; its filename and symlink metadata are still checked. The only
output is aggregate JSON: no matched value, file content, or path is printed.
Exit status is `0` only when the scan is complete and has zero findings, and is
nonzero otherwise. Provide any live exact credentials through their normal
named environment variables, never as command-line arguments.

## Compose six standalone full-environment jobs

When AP group artifact delivery is unavailable, export one successful
standalone job for each of E1 through E6 and compose them locally:

    python scripts/ap/compose_standalone_full.py \
      /exports/E1 /exports/E2 /exports/E3 /exports/E4 /exports/E5 /exports/E6 \
      --output-root /results/skillevolbench-local-full \
      --expected-benchmark-revision BENCHMARK_GIT_SHA \
      --expected-agenthub-revision AGENTHUB_GIT_SHA \
      --expected-split v1@8

The command accepts only standalone jobs (`group_id=null`) from
`megaflow-benchmark-dev`, requires one canonical complete episode per
environment, copies all six exports, and writes deterministic aggregate
metrics using the Agent-Hub group post-process formula. The resulting
`group.json` and `composition_manifest.json` explicitly use
`composition_mode=standalone_jobs_local_aggregate`; they are not evidence of a
real AP group. Every source and copied tree must pass the secret-safe safety
scanner. The manifest binds full-tree content digests and scan proofs, excludes
all AP `artifacts.json` signed-download metadata, and records the normalized
private permission policy (`0700` directories and `0600` regular files).

Audit the composed root with the same expected revisions and split:

    python scripts/ap/audit_full_group.py \
      /results/skillevolbench-local-full \
      --expected-benchmark-revision BENCHMARK_GIT_SHA \
      --expected-agenthub-revision AGENTHUB_GIT_SHA \
      --expected-split v1@8
