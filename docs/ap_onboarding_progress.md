# Agent Platform onboarding progress

Last updated: 2026-07-20 UTC

This document is the implementation log for onboarding SkillEvolBench to
Agent Platform (AP). It intentionally contains no API keys, registry passwords,
OSS credentials, or signed artifact URLs.

## Goal and acceptance boundary

Run the faithful SkillEvolBench lifelong protocol on AP even when the local
machine cannot run Docker:

- one AP instance represents one environment episode (`E1` ... `E6`);
- trials inside an episode run sequentially and share one environment-scoped
  skill library;
- the six independent environment episodes may run concurrently;
- AP artifacts preserve the report, skill-library history, replay store,
  events, retrieval traces, Harbor output, and per-trial verifier evidence;
- an AP `Succeeded` state is not sufficient: the run must also contain a
  verifier-backed result and the expected metrics and artifacts.

A one-task smoke is intentionally `scoreable=false`, `passed=false`, and
`task_score=0`. Onboarding is not complete until one canonical 30-primary-task
environment is scoreable and the six-environment group aggregation is tested.

## Repositories and pinned runtime

| Component | Branch or source | Current integration revision | Publication status |
| --- | --- | --- | --- |
| SkillEvolBench | `feat/ap-skillevolbench` | runtime `1ef46dc12e791bcffbe20bc35fc94a267dcfd798`; branch head `83ec227f8b46a862d235cf8fc6279f18c2500c79` adds a submission-output sanitizer fix | runtime packaged in immutable dataset `v1@3`; benchmark branch intentionally not pushed |
| Agent-Hub | `feat/skillevolbench` | `ed34889381d47a7065e7531d05025e38a4335011` | pushed and verified at the same remote revision |
| Harbor | official Git revision | `071281b3d931aafd6a5375fa7d5933e23054d784` (`0.20.0`) | installed and provenance-recorded by the AP template |

The Agent-Hub integration started from
`b7a94cadec1258f41774b454a546258ea14781e5`. Existing untracked inputs
(`ap_dev_docs/` and `docs/task_tiering_in_paper.md`) predate this work and must
be preserved.

## Confirmed runtime inputs

- AP base URL: `http://agentplatform.aliyun-inc.com`
- Development cluster: `benchmark-dev`
- AP template: `skillevolbench`
- Reference SGLang job: `dlc1xg8veyu370w6` in workspace `314370`
- Reference OpenAI-compatible endpoint:
  `http://10.101.224.230:22001/v1`
- Served model id reported by `/v1/models`:
  `serve-3.8-maxp-cpt-s1-0715-fable-1ep`

The endpoint is an ephemeral dependency. Re-probe `/v1/models` before every
submission and distinguish endpoint-capacity errors from verifier failures.

## Architecture decision

Do not submit 180 independent AP jobs. That would discard the skill state and
freeze boundary between tasks. Use six AP instances instead:

```text
AP group
  E1 job: 30 originals (+ optional 15 learning replays), sequential
  E2 job: 30 originals (+ optional 15 learning replays), sequential
  ...
  E6 job: 30 originals (+ optional 15 learning replays), sequential
```

Each job reports its environment-level evaluation success rate. Since every
environment contains the same number of evaluation tasks, the mean of the six
environment scores equals the full-benchmark evaluation success rate.

The task container is launched by a remote Docker daemon (DinD). Harbor passes
absolute host paths to that daemon for agent logs, verifier logs/rewards,
artifacts, skills, and injection context. Therefore the AP main container and
DinD sidecar must mount one named `emptyDir` at the same absolute path
(`/sevb-workspace`); copying files only into AP's output directory is not a
substitute for this state boundary.

## Dataset releases

All releases use the namespace `skillevolbench/skillevolbench`, contain exactly
six instance JSON files plus six per-environment `content.tgz` assets, and were
built from committed source only. Old versions are retained as immutable
debugging evidence and are not overwritten.

| Split | SkillEvolBench revision | Status and reason |
| --- | --- | --- |
| `v1@0` | `58ee5a1b75661d4b6faf98e9cbf984b7df710f4c` | initial publication; stale because its Harbor adapter used a pre-0.20 private `Trial` API |
| `v1@1` | `330698547fc7868d56d18138cfa9f38ccbaae660` | added Harbor 0.20 compatibility; stale because verifier failures could still collapse silently to reward zero and the DinD state mounts were not yet proven |
| `v1@2` | `ee0e585200a7aa5f4151e7e2803e10858f6f3acc` | fail-closed verifier semantics and shared state mounts; retained as Codex-runtime evidence |
| `v1@3` | `1ef46dc12e791bcffbe20bc35fc94a267dcfd798` | current release with pinned OpenCode 1.18.3 runtime and canonical OpenCode trajectory support |

For `v1@3`, two independent builds produced the same 13 files byte for byte.
The source archive SHA-256 is
`4d6d95f02adc615076c4eb2adba964d861b399423726f70ba752d293fcc0ffbe`
and the uncompressed Git archive tar SHA-256 is
`0db0bcc512a41f9fee5ca5de46959a4e221ca71816f824cfe8b97af4e2a616e2`.
The release manifest SHA-256 is
`c343bc372878c0feccbe9c1cdf92cf5e5f97c45afb85d1e210d11d15d9c57b85`.
All 13 objects were uploaded to versioned staging paths, checked against local
size and checksum/ETag evidence, and AP enumerated exactly `E1` through `E6`.

## Implementation changes after live smokes

### Harbor 0.20 adapter and mount contract

- Replaced the removed private `Trial._execute_agent` patch with the supported
  Harbor 0.20 hook and result flow.
- The global-library environment now accepts Harbor 0.20's `mounts` argument
  (while retaining the legacy compatibility input), preserves Harbor's three
  built-in mounts, and appends five skill mounts plus the injection mount.
  Object-level validation against the pinned Harbor build produced exactly
  nine mounts.
- Agent-Hub commit `661aec5535acac7b5198c616550dd00e941a38b8`
  added the same-path `/sevb-workspace` volume to main and DinD, a bidirectional
  bind sentinel, and copying of the shared run tree into AP artifacts.
- Agent-Hub commit `ee0b9c9ce9d54cfc2baa7ff58655f4222e160bd6`
  corrected the workspace init container to execute its setup through `sh`.

### Fail-closed verifier and lifecycle semantics

- A trial is valid only when there is no Harbor exception, a verifier result
  and non-empty rewards exist, `reward.txt` exists and contains a finite value
  in `[0, 1]`, Harbor's canonical reward agrees with that value, and a
  trajectory exists. Missing evidence raises an unscoreable error instead of
  becoming an ordinary reward of zero.
- All 180 task verifiers write `reward.txt`; 120 also write `reward.json`.
  The adapter no longer guesses an arbitrary first value from `reward.json`.
- Validation happens before replay-store, skill-library, strategy, or patch
  mutation. Failure finalization is non-mutating, so an infrastructure/model
  failure cannot be learned as benchmark experience.
- The AP runner records `n_verifier_backed_trials` and emits bounded,
  sanitized failure information.

### OpenCode runtime and provider contract

- The model server and CLI agent are separate layers: the same SGLang endpoint
  can serve Codex, OpenCode, or another compatible agent, but the CLI must still
  perform the filesystem/shell tool loop and emit a trajectory.
- A raw Chat Completions and function-call probe passed. The exact pinned
  OpenCode 1.18.3 CLI then completed a real write/read tool loop against the
  same server.
- OpenCode uses the non-reserved provider id `openai-compatible` with
  `@ai-sdk/openai-compatible`. The reserved `openai` id selected a
  Responses-specific path and failed against this generic Chat Completions
  adapter.
- Harbor stores only `${OPENAI_BASE_URL}` and `${OPENAI_API_KEY}` templates;
  OpenCode config references `{env:OPENAI_BASE_URL}` and
  `{env:OPENAI_API_KEY}`. Resolved credentials are not placed in agent kwargs
  or persisted runtime config.
- The existing `/root/.agents/skills` mount is reused. OpenCode lowercase tool
  names and camelCase parameters are normalized into the canonical trajectory;
  no duplicate skill mount is added, so the validated mount count remains nine.

### AP completion callback

The first live runs showed that the template's own `EXIT` trap shadowed AP's
injected `_final_exit`, leaving the AP metrics endpoint empty even when an
artifact `metrics.json` existed. Agent-Hub commit
`fa0ef7f7ec55a7782467c93eccf0deb4a1561e58` now delegates to `_final_exit`
after local artifact sync, fallback metrics, and sanitization. An executable
wrapper-contract test covers both callback status and copied artifacts.

## Live validation history

| Job | Dataset / template revision | Observed result | Disposition |
| --- | --- | --- | --- |
| `ap-cluster-verify-ad33803c8bd9456e-o4` | stock connectivity template | AP main reached the model and DinD pulled an image; stock DinD DNS checks failed | superseded by explicit DNS in the benchmark template |
| `ap-skillevolbench-91dbf9372a2b468a-o4` | `v1@0` / `f9348a6495c18fac4e087dd410d4c00557ac6787` | failed at `model-probe-dind`; curl config was not streamed correctly | fixed by Agent-Hub `ad9094651` |
| `ap-skillevolbench-aa243b2bfa8b43e4-o4` | `v1@0` / `fbab989778bd71ae2c20824161e4aef49c1fef3b` | host and DinD probes plus preflight passed, then the stale Harbor private API raised `AttributeError` | fixed in SkillEvolBench `3306985`; published as `v1@1` |
| `ap-skillevolbench-acab8fcd23fa4787-o4` | `v1@1` / stale branch resolution `fbab989778bd71ae2c20824161e4aef49c1fef3b` | AP reported `Succeeded` and the artifact was an explicit one-task partial, but AP metrics were empty and verifier/DinD evidence was incomplete; the model call also encountered endpoint demand | rejected as a valid Gate 4 smoke; drove callback, fail-close, and shared-workspace fixes |
| `ap-skillevolbench-4671f93cb2b6471e-o4` | `v1@2` / `661aec5535acac7b5198c616550dd00e941a38b8` | failed before main at workspace init, exit 127 | fixed by Agent-Hub `ee0b9c9ce` |
| `ap-skillevolbench-9637d96a722b4728-o4` | `v1@2` / exact `ee0b9c9ce9d54cfc2baa7ff58655f4222e160bd6` | Codex CLI exhausted five retries because the endpoint reported high demand; fail-closed metrics were non-empty and no learning state was mutated | valid failure-path evidence, but not a Gate 4 verifier-backed smoke |
| `ap-skillevolbench-555629ec612149dc-o4` | `v1@2` / Codex retry | repeated the same Codex high-demand failure with sanitized, unscoreable output | motivated testing a compatible CLI rather than changing the server |
| `ap-skillevolbench-8a619e8ee39d4949-o4` | `v1@3` / exact `ed34889381d47a7065e7531d05025e38a4335011` | succeeded in 784 seconds; OpenCode completed 15 trajectory steps and 26 tool calls; verifier reward was 1.0 with public 5/5, hidden 8/8, and process 5/5 | accepted Gate 4 smoke: callback is non-empty and intentionally partial/unscoreable, with one verifier-backed primary trial |

These runs deliberately use exact Agent-Hub commit ids where possible. A
moving branch name previously resolved to stale template code and is not
sufficient provenance for an acceptance run.

## Validation evidence

- SkillEvolBench: 64 tests pass, including a real verifier-backed
  reward-zero path and assertions that invalid trials cannot mutate learning
  state.
- Harbor 0.20 object-level mount validation: nine mounts with all built-in,
  skill, and injection targets present.
- Agent-Hub: eight template/group tests pass; `bash -n`, whitespace checks, and
  targeted AP path-migration lint rules R1-R6 pass.
- Dataset `v1@3`: deterministic two-build comparison passes; six remote assets,
  six indexes, and one release manifest were verified; AP discovery returns
  exactly six environment ids.
- The reusable AP onboarding skill passes its package validator after adding the
  OpenCode/provider and secret-interpolation lessons from this integration.
- The accepted OpenCode smoke contains the canonical trajectory, verifier logs
  and reward, complete report, replay record, event stores, and environment
  library history. It started with no retrieved skill and generated one active
  `systematic-error-diagnosis` skill from the successful T1 outcome; one patch
  was proposed and applied.
- A scan of the 103-file benchmark result payload found no live AP/model keys,
  bearer authorization values, Aliyun credential ids, signed URLs, or private
  keys. AP CLI export metadata is transport-layer material and is excluded from
  benchmark artifacts and handoff copies.
- Local strict preflight cannot be a complete runtime gate on this machine
  because it has no usable Docker daemon. The AP smoke is the authoritative
  DinD acceptance surface.

## Gate status and next steps

- [x] Gate 0: local/static validation and deterministic packaging.
- [x] Gate 1: safe one-task submission dry run with endpoint/model validation.
- [x] Gate 2: immutable `v1@3` publication and exact six-instance discovery.
- [x] Gate 3: current OpenCode template passed the shared-workspace probe plus
  host- and DinD-container model probes.
- [x] Gate 4: accepted fail-closed, verifier-backed one-task OpenCode smoke,
  job `ap-skillevolbench-8a619e8ee39d4949-o4`.
- [ ] Gate 5: run and inspect one complete 30-primary-task environment episode.
- [ ] Gate 6: run all six environments and validate retry-safe aggregation.
- [ ] Replace the bootstrap-built `agent-runtime:latest` with a pinned registry
  image if repeatability or runtime cost requires it.

Gate 4 was accepted from the exact template and dataset revisions, successful
bidirectional workspace and model probes, pinned Harbor provenance, one
verifier-backed trial, reward/logs, trajectory evidence, the complete artifact
run tree, and a non-empty AP metrics callback. Its benchmark status remains
`partial` and `scoreable=false` because the smoke is truncated.

## Open risks

- The model endpoint can be temporarily overloaded; such a call must remain an
  unscoreable infrastructure/model failure and must not update skill state.
- Bootstrapping `agent-runtime` in DinD depends on package mirrors and costs
  several minutes per cold run; a pinned prebuilt image would reduce drift.
- AP timeout and ephemeral storage must cover 30 or 45 sequential Harbor trials
  plus Docker build cache for a full environment.
- Gate 5 and Gate 6 have not run, so complete-episode timing, storage, and group
  aggregation remain unverified operationally.
- Logs and artifacts must continue to mask all model and platform credentials
  on both successful and failed exits.
