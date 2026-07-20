# SkillEvolBench v1@8 standalone full run

Last updated: 2026-07-21 UTC

## Purpose

This run is the canonical E1-E6 benchmark execution after AP's dynamic group
namespace repeatedly failed to upload artifacts.  It preserves the benchmark's
scientific state boundary while changing only the AP scheduling layer:

```text
six independent AP jobs
  each job = one environment
  each environment = 30 ordered primary tasks
                   + 15 same-session reflection turns
                   + one evolving environment-local skill library

local composition
  = the same macro aggregation over the six independent environment metrics
```

The result will be labelled `standalone_jobs_local_aggregate`; it is not an AP
group post-process.  No state is shared between environments in either route.

The failed AP group and platform evidence are documented in
[ap_group_artifact_incident_20260721.md](ap_group_artifact_incident_20260721.md).

## Immutable inputs

- Dataset: `skillevolbench/skillevolbench/v1@8`
- Benchmark revision: `94a496a3dee225d7d9f27ab5ba4801b652a93021`
- Agent-Hub revision: `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad`
- Harbor revision: `071281b3d931aafd6a5375fa7d5933e23054d784`
- OpenCode: `1.18.3`
- Baseline: `selfgen_in_session_always`
- Strategy: `chain`
- Order seed: `A`
- Replay: disabled
- Model: `serve-3.8-maxp-cpt-s1-0715-fable-1ep`

Dataset `v1@8` was built twice from committed source.  Both 13-file builds are
byte-identical.  The package-manifest SHA-256 is
`cf07058c68b4c276d87e52180d2e246a394419694dec6cde9e724a460b7e11a6`;
all 13 remote objects independently match local size and MD5, and AP discovery
returns exactly E1-E6.

Relative to `v1@7`, `v1@8` only hardens a post-verifier reflection timeout.  If
the already-verified solve evidence and exact same-session export can be proven,
the reflection becomes a terminal rejected outcome with reason
`reflection_agent_timeout`; it cannot mutate the skill library.  Missing solve,
verifier, session, workspace, or export evidence remains unscoreable.

## Route probe

Before the full submission, one non-canonical one-task probe was run:

- Job: `ap-skillevolbench-79be17cb71e1470d-o4`
- Idempotency key: `a31d37d3-b713-46f2-84d3-e42322609972`
- Namespace: `megaflow-benchmark-dev`
- Result: `Succeeded`
- Artifact: uploaded and downloaded successfully
- Expected benchmark status: partial, non-canonical, unscoreable

The downloaded probe contains one verifier-backed primary result and the
benchmark-owned evidence tree.  Its complete platform logs and export passed
the aggregate safety scanner.

## Canonical jobs

All six submissions were independently asserted at creation time to have
`group_id=null`, namespace `megaflow-benchmark-dev`, and the exact Agent-Hub
revision above.

| Environment | AP job | Idempotency key |
| --- | --- | --- |
| E1 | `ap-skillevolbench-dee69fde61334ffd-o4` | `5420ee4e-de5c-4387-b168-a5d0383dd9e7` |
| E2 | `ap-skillevolbench-52465faec12140fa-o4` | `4b1e6ffa-78ef-41b9-9c39-9ce8151dc483` |
| E3 | `ap-skillevolbench-0f14268d7e9949f3-o4` | `fc512fa6-0492-44d5-b3b2-ed51fac424f8` |
| E4 | `ap-skillevolbench-f7456a2080e44650-o4` | `d1ddad33-0a34-445e-a43b-5f5b938bc093` |
| E5 | `ap-skillevolbench-d1df0915fa3743fd-o4` | `235a7857-a977-4649-9bd1-42d8a204c98d` |
| E6 | `ap-skillevolbench-695c5efe0a9a4733-o4` | `e2ce22f6-f6e7-40a3-b930-f9dffbf52b03` |

## Acceptance workflow

Each terminal job is exported immediately to durable storage, including a
second-pass verified platform-log export.  Each complete job tree must pass the
read-only safety scanner before it enters the local composition.

Planned self-contained root:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/
  standalone-full-v1-8-20260721/
    composition_manifest.json
    group.json
    jobs/<six AP job ids>/...
    jobs/local-post-process/artifacts/output/metrics.json
```

Acceptance requires all of the following:

- six successful standalone jobs and six downloadable `result.tgz` objects;
- exact E1-E6 coverage, with one canonical environment artifact per ID;
- 180 verifier-backed primary trials and zero replay/shadow trials;
- 90 terminal same-session reflection outcomes;
- exact task order, role sequence, library freeze boundary, verifier evidence,
  session continuity, provenance, and sanitizer-integrity checks;
- a local aggregate that exactly matches recomputation from the six raw metrics;
- manual inspection of all failure-to-success and success-to-failure transfers,
  rejected/no-op reflections, applied-but-not-retrieved skills, and final skill
  files.

Transition counts remain observational.  They answer whether a generated skill
was present, retrieved, and followed by success or failure on a different next
input.  They do not establish a causal effect without a matched no-reflection
or no-retrieval control.
