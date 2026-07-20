# Agent Platform onboarding progress

Last updated: 2026-07-21 UTC

This is the credential-free implementation log for onboarding SkillEvolBench
to Agent Platform (AP). Do not add API keys, registry passwords, OSS
credentials, signed artifact URLs, or raw transport metadata to this file.

## Current status

The AP runtime now passes a complete ordered T1-T6 family diagnostic with:

- six verifier-backed primary trials in one stateful AP job;
- same-agent, same-session solve and reflection for T1-T3;
- a shared environment skill library, frozen between T3 and T4;
- no reflection or library mutation during T4-T6;
- complete trajectories, verifier evidence, library history, event stores, and
  platform logs in the downloaded artifacts;
- a validated runtime-to-delivered digest manifest for sanitizer rewrites.

Accepted family job: `ap-skillevolbench-8199e9ce930845fb-o4`. Its detailed
model and verifier analysis is in [ap_family_smoke_v1_7.md](ap_family_smoke_v1_7.md).

This is a non-canonical `family_smoke`, so its correct benchmark status is
`completed_noncanonical`, `scoreable=false`, `passed=false`, and
`task_score=0`. It is stronger than a one-task bootstrap smoke, but is not a
canonical 30-primary-task environment. Canonical one-environment and
six-environment validation remain open.

## Active canonical full run

The six-environment canonical run was submitted on 2026-07-21 at 02:20 CST:

- suite: `skillevolbench-full-selfgen-v1-7-20260721`;
- group: `group-3fa2a5793bcb4237ad2ceab701167100-o4`;
- idempotency key: `37d06fef-309c-4a71-bdca-6abbfc53ccb6`;
- exact Agent-Hub/template commit:
  `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad`;
- dataset: `skillevolbench/skillevolbench/v1@7`;
- concurrency: six independent environment jobs;
- per environment: 30 primary tasks, 15 same-session learning reflections,
  no replay;
- post-process job: `ap-group-post-process-ce39bd7f868b50b5`.

| Environment | AP job |
| --- | --- |
| E1 | `ap-skillevolbench-7a8bb89996764d47-o4` |
| E2 | `ap-skillevolbench-a83b30f814d54d75-o4` |
| E3 | `ap-skillevolbench-e55f84389a954c19-o4` |
| E4 | `ap-skillevolbench-bcec361cc8e84e22-o4` |
| E5 | `ap-skillevolbench-bc6f555a627745f8-o4` |
| E6 | `ap-skillevolbench-9ac26c01ebea4382-o4` |

The dry run enumerated exactly E1-E6 and the live submission reported six
submitted, zero failed. A stable UUID4 was supplied because AP CLI 0.1.16 does
not retry POST automatically; reuse this exact key after an ambiguous transport
failure rather than issuing an unkeyed duplicate submission.

The six jobs passed asset download, host and DinD model probes, shared-mount
probe, strict preflight, and entered their stateful 30-task episodes. They are
still running; no retry has been issued. Full artifacts will be preserved under
`/cpfs02/user/zhangfengji.zfj/workspace/skillevolbench_ap_results/` because the
`/cpfs01` filesystem currently reports no available capacity.

## Full-run acceptance tooling

Three read-only helpers make the final decision reproducible:

- `scripts/ap/audit_full_group.py` verifies exact E1-E6 completeness, 180
  primary trials, zero replay, 90 terminal same-session reflections, task
  order/roles, freeze boundaries, verifier evidence, trajectories, provenance,
  sanitizer digests, and the raw group post-process result. It recomputes group
  `evaluation_sr`, `task_score`, and `passed` from the six environment metrics.
- `scripts/audit_skill_utility.py` links every reflection result and applied
  skill version to the next different input, retrieval/use evidence, and its
  verifier outcome. Its transition results are explicitly observational; a
  matched control is still required for a causal skill-effect claim.
- `scripts/ap/export_platform_logs.py` works around the AP CLI 0.1.16 log export
  bug by using the server's 500-entry page limit through terminal
  `next_offset=null`, followed by a second API pass and local hash/size checks.

The post-process job must be exported into the group's `jobs/<job-id>/`
directory. Its benchmark-owned
`artifacts/output/metrics.json` is authoritative; the adjacent AP wrapper
`metrics.json` is transport metadata and must not shadow it.

## Repositories and pinned runtime

| Component | Branch or source | Accepted revision | Publication status |
| --- | --- | --- | --- |
| SkillEvolBench runtime | `feat/ap-skillevolbench` | `a0972c3b98f724e6b89e35ac974c142368a0c6d0` | packaged in immutable dataset `v1@7`; benchmark branch intentionally not pushed |
| Agent-Hub template | `feat/skillevolbench` | `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad` | pushed; remote branch resolves to this exact revision |
| Harbor | official Git revision | `071281b3d931aafd6a5375fa7d5933e23054d784` (`0.20.0`) | installed and provenance-recorded by the AP template |
| OpenCode | npm runtime | `1.18.3` | pinned in template and Harbor fallback |

The Agent-Hub work started from
`b7a94cadec1258f41774b454a546258ea14781e5`. Existing untracked inputs
`ap_dev_docs/` and `docs/task_tiering_in_paper.md` predate this work and must be
preserved.

## Confirmed runtime inputs

- AP base URL: `http://agentplatform.aliyun-inc.com`
- Development cluster: `benchmark-dev`
- AP template: `skillevolbench`
- Reference SGLang job: `dlc1xg8veyu370w6` in workspace `314370`
- OpenAI-compatible endpoint used by the accepted run:
  `http://10.101.224.230:22001/v1`
- Served model id:
  `serve-3.8-maxp-cpt-s1-0715-fable-1ep`

The model endpoint is ephemeral. Probe `/v1/models` before every submission and
distinguish endpoint availability/capacity failures from task-verifier
failures.

## Scientific and platform state boundaries

The canonical AP execution unit is one environment episode, not one task:

```text
AP group
  E1 job: 30 primary tasks (+ optional replay block), sequential
  E2 job: 30 primary tasks (+ optional replay block), sequential
  ...
  E6 job: 30 primary tasks (+ optional replay block), sequential
```

Submitting 180 independent AP jobs would discard the shared skill library,
ordering, and freeze boundary. The six environment jobs are independent and
may run concurrently; trials inside one environment must remain sequential.

For the user's same-agent experiment, the setting is
`selfgen_in_session_always`:

```text
per learning task:
  solve turn -> official verifier -> resume exact OpenCode session
             -> bounded reflection turn -> host validates/applies candidate

after T3:
  freeze library -> T4/T5/T6 consume it without reflection
```

“Same session” means a task's solve and reflection share one session. Different
tasks use different sessions but share the environment library. Session IDs,
trajectory/export prefix continuity, container identity, and an unchanged task
workspace are verified. A continuity failure is unscoreable. A malformed skill
candidate is recorded as model behavior and rejected without corrupting the
library.

The explicit family diagnostic selects one family ID such as `E1-LS1`, asserts
exact T1-T6 order and canonical/enriched/variant/context-shift/adversarial/
composition roles, forbids replay, and remains non-canonical. It must not be
implemented as `max_tasks=6`, which would select the wrong environment-wide
prefix.

## Container and artifact architecture

Harbor launches task containers through the AP job's remote Docker daemon
(DinD). Harbor passes absolute host paths for agent logs, verifier output,
artifacts, skills, and injection context. The AP main container and DinD
sidecar therefore mount one named `emptyDir` at the identical absolute path
`/sevb-workspace`. A bidirectional sentinel probe validates the mount before
execution.

The template stages are: validate inputs, wait for DinD, download and validate
the pinned asset, install dependencies, probe the model from the AP main
container, prepare the agent runtime, probe from a DinD task container, run
strict benchmark preflight, execute the episode, validate metrics, sanitize
artifacts, and delegate to AP's injected completion callback. Every premature
exit produces bounded, sanitized, unscoreable fallback metrics.

## Dataset releases

All releases use `skillevolbench/skillevolbench`, contain six instance JSON
files plus six per-environment `content.tgz` assets, and are built from
committed source only. Releases are immutable and never overwritten.

| Split | SkillEvolBench revision | Status |
| --- | --- | --- |
| `v1@0` | `58ee5a1b75661d4b6faf98e9cbf984b7df710f4c` | stale pre-Harbor-0.20 adapter |
| `v1@1` | `330698547fc7868d56d18138cfa9f38ccbaae660` | Harbor 0.20 compatibility; incomplete fail-close/mount evidence |
| `v1@2` | `ee0e585200a7aa5f4151e7e2803e10858f6f3acc` | fail-closed verifier and shared-state mounts |
| `v1@3` | `1ef46dc12e791bcffbe20bc35fc94a267dcfd798` | OpenCode 1.18.3 runtime and canonical trajectories |
| `v1@4` | `a730b3b1155d26183374713df3b7ceac97064b85` | first same-session family protocol; exposed stopped-container snapshot issue |
| `v1@5` | `5eae7a574006fd0303b5181a9b9ee3216b67c4cd` | stopped-container fix; exposed OpenCode session-export compatibility issue |
| `v1@6` | `322225dba44a668a36e6ead9b22f5836a494218f` | first completed family run; artifact redaction corrupted ordinary `EMPTY` identifiers and audit hashes |
| `v1@7` | `a0972c3b98f724e6b89e35ac974c142368a0c6d0` | accepted family diagnostic with fail-closed, manifest-backed sanitization |

For `v1@7`, two independent builds produced the same 13 files byte for byte.
The release-manifest SHA-256 is
`744c2f051441ac000c75a7ba752aa0452feb84bba01cee912ef7adbf35b06c06`.
All 13 remote objects were checked by size and ETag/MD5; AP discovery returned
exactly `E1` through `E6`.

## Key implementation decisions

### Fail-closed verifier and learning mutation

A trial is valid only if Harbor has no exception, verifier rewards exist,
`reward.txt` is finite and in `[0,1]`, the canonical Harbor reward agrees, and
a trajectory exists. Validation happens before replay-store, skill-library,
strategy, or patch mutation. Missing evidence becomes an unscoreable error,
never an ordinary task failure or a learnable experience.

### OpenCode provider and secret plumbing

The SGLang endpoint and CLI agent are separate layers. Raw API reachability did
not prove a real filesystem/shell tool loop, so the exact pinned OpenCode CLI
was exercised against the endpoint. It uses a non-reserved
`openai-compatible` provider backed by `@ai-sdk/openai-compatible`; the reserved
`openai` provider selected an incompatible Responses path.

Harbor stores `${OPENAI_BASE_URL}` and `${OPENAI_API_KEY}` templates, and
OpenCode references `{env:OPENAI_BASE_URL}` and `{env:OPENAI_API_KEY}`. Resolved
credentials are not persisted in kwargs or runtime configuration. OpenCode's
lowercase tool names and camelCase arguments are normalized into canonical
trajectories.

### Same-session reflection

The task container is stopped after solve but not destroyed. The host snapshots
`/root/task`, runs the verifier in isolation, restarts the same container, and
resumes the recorded OpenCode session with bounded verifier feedback. The model
may write only one candidate JSON file. The host validates JSON, paths, sizes,
skill frontmatter, family ownership, and secret safety before the freeze
controller applies it.

### Sanitized artifact integrity

Generic no-auth placeholders such as `EMPTY` cannot be used as global exact
redaction tokens because they occur in ordinary code. Before Harbor starts, the
runner replaces such placeholders with a high-entropy ephemeral
`sevb-no-auth-*` value. The primary sanitizer then:

- rejects unsafe short secret values;
- scans all regular files plus binary, symlink-name, and symlink-target cases;
- atomically rewrites stable files and snapshots an actively written
  `logs/main.log` by inode replacement;
- writes `sanitization_manifest.json` with runtime and delivered SHA-256/size
  for every changed file;
- fails closed if sanitization or manifest creation fails.

Agent-Hub requires the benchmark-generated manifest. A missing/failing primary
sanitizer discards artifacts instead of silently falling back after partial
writes. A bootstrap-only sanitizer remains available for failures before the
benchmark source is extracted.

## Live validation history

| Job | Dataset / Agent-Hub revision | Result and disposition |
| --- | --- | --- |
| `ap-skillevolbench-8a619e8ee39d4949-o4` | `v1@3` / `ed34889381d47a7065e7531d05025e38a4335011` | accepted one-task Gate 4 smoke; verifier reward 1.0, complete trajectory, explicitly partial/unscoreable |
| `ap-skillevolbench-ad7492fa642b4039-o4` | `v1@4` / `9e9c6219f0d4cc800e86b4fd5d85b77954cfff67` | failed before a primary result; exposed task snapshot against a stopped container |
| `ap-skillevolbench-df78d870f5224353-o4` | `v1@5` / `071eea52d84ae0c2de9196361e18dbd99d57488a` | failed before a primary result; exposed pinned OpenCode prompt/session-export shape drift |
| `ap-skillevolbench-6cea7fc3b09446d2-o4` | `v1@6` / `d8a8154efac7776ec8f52037f03a278b29beadca` | six trials completed, but artifact audit rejected global `EMPTY` replacement and unexplained reflection-hash changes |
| `ap-skillevolbench-8199e9ce930845fb-o4` | `v1@7` / `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad` | accepted T1-T6 family diagnostic; protocol, sanitizer manifest, frozen library, trajectories, and logs audit passed |

Earlier bootstrap failures are retained in AP but are superseded by the
accepted one-task and family runs. Exact immutable commits are used because a
moving Agent-Hub branch previously resolved to stale template code.

## Accepted family evidence

- AP job ran from `2026-07-21T01:19:41.224` through
  `2026-07-21T01:53:08.907` (about 33.5 minutes).
- Six-trial episode completed in about 26 minutes 34 seconds.
- T1/T2/T3 rewards: `1.00`, `1.00`, `1.00`.
- T4/T5/T6 official rewards: `0.35`, `0.90`, `0.75`. Contract-level
  inspection found implementation-coupled verifier false negatives in all
  three: T4's delivered CI tests and real FastAPI webhook pass, while T5/T6
  pass every functional verifier test.
- T1 and T3 reflections completed; T2 was correctly rejected for invalid YAML
  frontmatter. All three same-session continuity proofs passed.
- One final active `systematic-error-diagnosis` skill was created at T1 and
  revised at T3; T2-T6 retrieved and explicitly referenced it.
- The library was frozen once between T3 and T4; T4-T6 did not mutate it.
- The downloaded tree is about 112 MiB with 1,479 files including hidden Git
  state. All six solve trajectories and all three reflection audits are present.
- The sanitizer manifest validates 45 changed files, including runtime-to-
  delivered hash mappings for four T2 audit files. A whole-output scan found no
  live platform/model/OSS secrets, signed URLs, ephemeral sentinels, or private
  keys inside `artifacts/output/`.
- AP CLI `0.1.16` initially failed platform-log export because it requested
  1,000 entries while the service maximum is 500. Logs were re-exported with
  pagination and independently verified: 3,273 entries across five containers,
  with terminal `next_offset=null` recorded in
  `logs/pagination_manifest.json`. Benchmark trajectories in `result.tgz` were
  already complete and unaffected.

## Validation results

- SkillEvolBench: 144 tests passed at runtime revision `a0972c3`.
- Agent-Hub: 11 template/group tests passed at `1e10fc0`; `bash -n`, Ruff,
  whitespace, and targeted path-migration lint passed.
- Dataset `v1@7`: deterministic two-build comparison and all 13 remote-object
  checks passed; AP enumerated exactly six instances.
- Family artifact audit: passed task count/order, verifier bundles, replay and
  injection evidence, same-session proof, sanitizer hash mapping, single
  freeze/unfreeze, frozen Git tree, and secret scan.
- Reusable `ap-benchmark-onboarding` skill: package validation passed after
  adding the same-session, sanitizer-manifest, no-auth sentinel, and AP log
  pagination lessons.
- Current branch after adding the three reusable acceptance helpers: 163 tests
  passed, plus Ruff, formatting, byte-code compilation, and whitespace checks.

Local strict preflight is not an authoritative runtime gate on this machine
because it has no usable Docker daemon. The AP DinD run is the live acceptance
surface.

## Gate status

- [x] Gate 0: local/static checks and deterministic packaging.
- [x] Gate 1: safe dry-run submission with endpoint/model validation.
- [x] Gate 2: immutable `v1@7` publication and six-instance discovery.
- [x] Gate 3: shared-workspace plus host and DinD model probes.
- [x] Gate 4: one-task fail-closed, verifier-backed, explicitly unscoreable
  smoke.
- [x] Diagnostic Gate 4.5: explicit non-canonical T1-T6 family with same-session
  reflection, freeze boundary, complete trajectories, and artifact-integrity
  audit.
- [ ] Gate 5: one canonical 30-primary-task environment episode.
- [ ] Gate 6: all six environments with retry-safe aggregation. The canonical
  E1-E6 group above is currently running and is not accepted until every
  environment artifact plus group post-processing passes audit.
- [ ] Optional hardening: replace the bootstrap-built
  `agent-runtime:latest` with a pinned registry image.

## Next commands

Re-run the same family only for a controlled replication or paired baseline,
not as an immediate same-input retry:

```bash
python scripts/ap/submit.py \
  --scope family \
  --environment-id E1 \
  --family-id E1-LS1 \
  --split 'v1@7' \
  --agenthub-ref 1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad \
  --harbor-agent opencode \
  --model serve-3.8-maxp-cpt-s1-0715-fable-1ep \
  --model-base-url http://10.101.224.230:22001/v1 \
  --concurrency 1
```

The command reads AP/model credentials from the environment; never place them
on the command line or in this document. Add `--dry-run` before any new live
configuration. For the next operational gate, replace `--scope family` and the
family selector with `--scope environment` after re-probing the endpoint and
confirming timeout/storage budget.

For the user's causal question, first run matched family pairs across multiple
families and seeds: `selfgen_in_session_always` versus a no-reflection setting,
with identical tasks/order/model. Compare official strict results and
outcome-only results separately. This is more informative than repeatedly
running the same input, and is required before attributing success or harm to a
generated skill.

## Remaining risks

- The endpoint may be overloaded or replaced; such failures must remain
  unscoreable and non-mutating.
- Runtime image bootstrapping depends on package mirrors and consumes several
  minutes; a pinned image would reduce drift.
- Gate 5/6 timing, storage, retry de-duplication, and group scoring have not yet
  been observed live.
- One of three reflection candidates was lost to malformed YAML. A bounded
  schema-repair retry would improve author reliability, but adding it changes
  the experimental setting and must be treated as an explicit variant.
- The audited E1-LS1 evaluation verifiers are implementation-specific: T4
  requires an undocumented helper and golden test-edit strategy, T5 searches
  for one source substring, and T6 requires `quote_plus` over an equivalent
  tested encoding. Preserve official scores, but correct these verifiers and
  report functional/process/contract-audit outcomes separately before drawing
  model-capability conclusions.
- The final library manifest's evidence counters remain zero even though replay
  records, trajectories, and `full_report.json` record five real uses. Treat the
  replay-derived evidence as authoritative for this run and wire or remove the
  stale manifest counters before relying on them downstream.
- The top-level AP export transport metadata is outside the sanitized benchmark
  tree and may contain expiring artifact URLs. Do not publish it; hand off
  `artifacts/output/` instead.
