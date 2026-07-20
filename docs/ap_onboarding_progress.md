# Agent Platform onboarding progress

Last updated: 2026-07-20 UTC

This document is the implementation log for onboarding SkillEvolBench to
Agent Platform (AP). It intentionally contains no API keys, registry passwords,
or OSS credentials.

## Goal

Run the faithful SkillEvolBench lifelong protocol on AP even when the local
machine cannot run Docker:

- one AP instance represents one environment episode (`E1` ... `E6`);
- trials inside an episode run sequentially and share one environment-scoped
  skill library;
- the six independent environment episodes may run concurrently;
- AP artifacts preserve the full report, skill-library history, replay store,
  events, retrieval traces, Harbor output, and per-trial verifier evidence.

## Repositories and branches

| Repository | Branch | Starting revision |
| --- | --- | --- |
| SkillEvolBench | `feat/ap-skillevolbench` | upstream `main` at onboarding start |
| Agent-Hub | `feat/skillevolbench` | `b7a94cadec1258f41774b454a546258ea14781e5` |

Existing untracked inputs (`ap_dev_docs/` and
`docs/task_tiering_in_paper.md`) predate this work and must be preserved.

## Confirmed runtime inputs

- AP base URL: `http://agentplatform.aliyun-inc.com`
- Development cluster header: `X-Cluster:benchmark-dev`
- `harbor` template is readable in `benchmark-dev`.
- Reference SGLang job: `dlc1xg8veyu370w6` in workspace `314370`.
- Reference OpenAI-compatible endpoint:
  `http://10.101.224.230:22001/v1`
- Served model id reported by `/v1/models`:
  `serve-3.8-maxp-cpt-s1-0715-fable-1ep`

The endpoint is a live, ephemeral dependency. Re-probe `/v1/models` before
every AP submission.

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

## Work log

### 2026-07-20: discovery and setup

- Read the AP onboarding manual and colleague notes in `ap_dev_docs/`.
- Updated Agent-Hub to current `origin/main` and verified a clean worktree.
- Probed candidate clusters. `benchmark-dev` resolves the current `harbor`
  template; `hk-benchmark-dev` and `hk-test` require credentials in the current
  shell and are not used for the initial integration.
- Verified the reference DLC job is running and its SGLang `/v1/models`
  endpoint responds.
- Created isolated feature branches in both repositories.
- Initialized the reusable Codex skill
  `$CODEX_HOME/skills/ap-benchmark-onboarding`.

### 2026-07-20: episode runner and measurement contract

- Added `environment_id` filtering through the run schema, scheduler, CLI,
  and lifelong runner. A selected episode preserves the canonical 30 primary
  tasks and optional 15 learning replays.
- Repaired two correctness issues found while preparing AP execution:
  final environment maintenance is now awaited before report generation, and
  environment-scoped library manifests are aggregated correctly.
- Added AP `metrics.json` output with a strict distinction between a complete,
  scoreable 30-task episode and a truncated infrastructure smoke.
- Added paired same-task replay outcomes (`F->S`, `S->F`, `F->F`, `S->S`) as
  a local recovery diagnostic.
- Added a separate cross-task transition diagnostic: after an applied skill
  revision, pair the triggering task with the next different task in the same
  family. This directly exposes failure-to-success recovery and
  success-to-failure regression on changed inputs. It is observational and
  must be compared with a no-revision control before causal interpretation.
- Made the agent-runtime Ubuntu mirror configurable so an AP build can use a
  cluster-local mirror instead of the original hard-coded AWS mirror.
- Local validation currently passes: 15 targeted tests, Python compilation,
  shell syntax checks, and `git diff --check`.

### 2026-07-20: AP template, packaging, and live connectivity

- Added a deterministic dataset packager. Every E1-E6 asset contains the same
  complete Git archive (all 30 families / 180 tasks), a full commit id, and
  SHA-256 provenance; only the episode metadata differs. Tracked
  credential-shaped files fail the package build, and untracked local docs or
  credentials never enter `git archive`.
- Added a safe AP submission helper. Its default is a one-task E1 smoke,
  verifies the served model through `/v1/models`, uses `responses` for Codex,
  and makes all truncated output explicitly unscoreable.
- Implemented `task/skillevolbench` in Agent-Hub with a DinD sidecar, OSS
  download, runtime preparation, host and task-container model probes, strict
  preflight, failure-safe metrics, artifact masking, and six-environment group
  aggregation.
- Ran live AP connectivity job
  `ap-cluster-verify-ad33803c8bd9456e-o4` on `benchmark-dev`. The main AP
  container successfully called the reference SGLang server
  (`model_status=ok`), and DinD successfully pulled its probe image. The stock
  cluster-verify DinD daemon had no usable DNS, so DNS/GitHub/npm/PyPI checks
  failed. The SkillEvolBench template explicitly configures the documented AP
  internal DNS servers; its in-container probe will be the acceptance test.
- AP rejected a dynamic attempt to override the stock probe's sidecar args, so
  the DNS fix cannot be validated through `cluster-verify`; it must be tested
  after the feature Agent-Hub branch is pushed.
- Current local validation: 34 tests pass in SkillEvolBench; Agent-Hub group
  aggregation has 3 passing end-to-end tests; both repositories pass shell
  syntax and whitespace checks.

## Planned implementation

- [x] Add a first-class environment filter to the scheduler/runner and CLI.
- [x] Add single-environment order invariants and tests.
- [x] Make report generation understand environment-scoped libraries.
- [x] Await final environment maintenance before report generation.
- [x] Add an AP runner entrypoint and standard `metrics.json` output.
- [x] Add same-task replay and changed-input cross-task transition metrics.
- [x] Add deterministic six-instance dataset packaging.
- [ ] Add a pinned runner image and DinD-visible `agent-runtime` image flow.
- [x] Add `task/skillevolbench` to Agent-Hub.
- [x] Validate configuration without Docker.
- [x] Verify AP main-container access to the reference SGLang endpoint.
- [ ] Verify AP DinD-container DNS and SGLang access through the new template.
- [ ] Build/push images and assets using an environment with Docker/ACR access.
- [ ] Submit and inspect a one-task infrastructure smoke.
- [ ] Submit and inspect one complete environment episode.
- [ ] Submit the six-environment group and aggregate reports.
- [ ] Finish and validate the reusable onboarding skill.
- [ ] Append stable lessons to the allowed memory extension directory.

## Open risks

- The current machine has no working Docker daemon, so image builds must run in
  DSW/DLC/AP infrastructure.
- Every task Dockerfile uses `FROM agent-runtime:latest`; the AP DinD daemon
  must pull a pinned registry image and retag it locally before Harbor builds.
- AP job timeout and ephemeral storage must cover 30 or 45 sequential Harbor
  trials plus build cache.
- Logs and artifacts must mask all model and platform credentials.
