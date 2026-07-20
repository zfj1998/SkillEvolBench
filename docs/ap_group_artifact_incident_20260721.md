# AP group artifact upload incident (2026-07-21)

## Outcome

The first canonical six-environment SkillEvolBench run completed multiple
environment episodes, but its results cannot be accepted because AP discarded
their benchmark-owned artifacts after the platform `artifact-uploader` received
OSS `403 AccessDenied` responses.

This is an AP group-execution storage incident, not a benchmark verifier or
artifact-size failure.  Until AP fixes the group uploader identity, canonical
episodes are being submitted as six independent AP jobs and composed locally.
The scientific state boundary is unchanged: one independent job still runs all
30 tasks and 15 same-session reflections for one environment sequentially.

## Affected submission

- Cluster: `benchmark-dev`
- Group: `group-3fa2a5793bcb4237ad2ceab701167100-o4`
- Suite: `skillevolbench-full-selfgen-v1-7-20260721`
- Group namespace: `ap-job-ns-63`
- Agent-Hub revision: `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad`
- Dataset: `skillevolbench/skillevolbench/v1@7`

Confirmed uploader failures:

| Environment | Job | Attempt | Benchmark state before upload | AP result |
| --- | --- | ---: | --- | --- |
| E1 | `ap-skillevolbench-7a8bb89996764d47-o4` | 0 | canonical 30/30 primary, 15/15 terminal reflections | `ARTIFACT_UPLOAD_FAILED` |
| E2 | `ap-skillevolbench-a83b30f814d54d75-o4` | 0 | canonical 30/30 primary, 15/15 terminal reflections | `ARTIFACT_UPLOAD_FAILED` |
| E3 | `ap-skillevolbench-e55f84389a954c19-o4` | 0 | stopped at 11/30 after a reflection timeout | `ARTIFACT_UPLOAD_FAILED` |
| E4 | `ap-skillevolbench-bcec361cc8e84e22-o4` | 0 | canonical 30/30 primary, 15/15 terminal reflections | `ARTIFACT_UPLOAD_FAILED` |
| E5 | `ap-skillevolbench-bc6f555a627745f8-o4` | 0 | canonical 30/30 primary, 15/15 terminal reflections | `ARTIFACT_UPLOAD_FAILED` |

After the fifth identical uploader failure, the E3 retry and the original E6
job were cancelled at lower bounds of 14/30 and 23/30 completed primary tasks.
Their continuation could not produce acceptable artifacts in the affected
namespace and would only delay the replacement run.  Cancellation events,
fallback state, and complete platform logs were retained and safety-scanned.
The automatically triggered post-process job
`ap-group-post-process-ce39bd7f868b50b5` was also cancelled after remaining
Pending for 34 minutes: none of its six inputs had a downloadable benchmark
artifact, so it could not produce an authoritative aggregate.

In each case, the uploader successfully enumerated and compressed the output,
then failed while opening the standard AP results object.  E1, E3, and E4
archives were respectively 45.29 MiB, 16.48 MiB, and 24.20 MiB.  The failure
therefore spans both complete and incomplete episodes and is not caused by one
oversized artifact.

## Control and routing evidence

The accepted family smoke
`ap-skillevolbench-8199e9ce930845fb-o4` used the same template revision and the
same platform uploader image.  It ran in `megaflow-benchmark-dev` and uploaded a
15.77 MiB archive successfully.

Recent AP history supplies a cross-template control: standalone jobs route to
`megaflow-benchmark-dev` and can upload, while group jobs route to dynamic
`ap-job-ns-*` namespaces.  A separate group template failed from a dynamic
namespace even for a roughly 22 KiB object using ordinary `PutObject`.  This
rules out SkillEvolBench output volume and multipart upload as the common cause.

The strongest current diagnosis is a missing or incorrect OSS write policy for
the platform-managed uploader identity injected into dynamic group namespaces.
Template `secret_env` belongs to the benchmark main container and is not a
supported override for AP's managed uploader.

## Evidence retained

AP fallback metrics, events, and complete paginated platform logs are stored
under:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/diagnostics/
```

Each retained export has a sibling aggregate safety-scan report.  The raw AP
`artifacts.json` transport metadata is intentionally not inspected or
published.  The lost `result.tgz` objects cannot be reconstructed from logs.

## Requested AP-side repair

1. Inspect the platform-managed `artifact-uploader` credential/RAM policy for
   namespace `ap-job-ns-63` and the dynamic group namespace provisioning path.
2. Confirm it can write the standard per-job results prefix in the staging
   results bucket, including both `PutObject` and multipart-init operations.
3. Check the corresponding dynamic namespace Secrets/service identity, not the
   benchmark template's main-container `secret_env`.
4. Validate with one small group job and one multipart-sized group job before
   asking benchmark owners to rerun long episodes.

Changing a namespace Secret may not update credentials already mounted in
running pods.  A central RAM-policy correction may rescue an existing identity;
otherwise affected episodes require a rerun after the platform repair.

## Temporary benchmark route

Dataset `v1@8` packages the reflection-timeout hardening at benchmark revision
`94a496a3dee225d7d9f27ab5ba4801b652a93021`.  It was built twice byte-for-byte,
published immutably, verified object-by-object, and AP discovers exactly E1-E6.

The temporary route is:

1. verify one short standalone job lands in `megaflow-benchmark-dev` and uploads;
2. submit E1-E6 as six separate complete environment jobs;
3. export and safety-scan every job immediately after completion;
4. create an explicitly labelled `standalone_jobs_local_aggregate` composition;
5. recompute the same six-environment metrics and run the full artifact audit.

The local composition must never be represented as an AP group post-process.
It changes only orchestration and storage routing, not task order, model
configuration, skill evolution, or the environment-level scoring unit.
