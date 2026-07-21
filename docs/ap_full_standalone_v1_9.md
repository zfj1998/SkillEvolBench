# SkillEvolBench v1@9 standalone full run

Last updated: 2026-07-21 UTC

## Purpose

This is the replacement canonical E1-E6 run after the first standalone full
attempt (`v1@8`) exposed two different fail-closed outcomes:

- E2 stopped in solve phase when `E2-LS5-T2` reached the task's declared
  600-second agent timeout.  No verifier or reflection ran for that task.  The
  same E2 episode completed under `v1@7`, so this is treated as a stochastic
  model/tool-loop timeout rather than a deterministic task defect.
- E3 completed solve and verifier for `E3-LS4-T2` (reward `0.8167`), but the
  post-verifier continuity validator rejected OpenCode's automatic compaction
  messages.  The solve/full prefixes and session IDs matched; the old
  validator incorrectly required every message after the reflection prompt to
  be an assistant message.

The E3 issue is a benchmark adapter compatibility bug, so a successful retry
of only E3 would not be a canonical scientific result.  `v1@9` fixes the
validator and starts all six environments fresh from empty, independent skill
libraries.

## Immutable inputs

- Dataset: `skillevolbench/skillevolbench/v1@9`
- Benchmark revision: `8c7889349ca277af2a53f47411f70a06d63a3007`
- Agent-Hub revision: `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad`
- OpenCode: `1.18.3`
- Baseline: `selfgen_in_session_always`
- Strategy: `chain`
- Order seed: `A`
- Within-environment replay: disabled
- Replay evaluation: disabled
- Model: `serve-3.8-maxp-cpt-s1-0715-fable-1ep`
- AP namespace: `megaflow-benchmark-dev`
- AP group: none; six standalone jobs are composed locally after acceptance

The source revision was packaged twice.  Both 13-file local builds are byte
identical.

- Package manifest SHA-256:
  `8ea716fbb5f0b8f17cb3fdb151789f47e876695fe47626565309367106821ea0`
- Source archive SHA-256:
  `189dfcd37d68bb20e83eb1052ea7e9297d0d63b563c2a4bf0f9668c61b20be71`
- Git archive tar SHA-256:
  `6077290347e44f642fa92865bdc1e32ec63ec128cfc169304bcff1ee31953de5`
- AP-required remote objects: 12; every object independently matched local
  content length and single-part ETag/MD5.
- AP discovery: exactly `E1` through `E6`.

Durable publication evidence:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/datasets/
  v1@9-build-a/
  v1@9-build-b/
  v1@9-upload-verification.json
```

## Continuity fix

The adapter now records minimal OpenCode control metadata in the canonical
trajectory and validates both that trajectory and the raw session export.  It
accepts only the pinned automatic-compaction state machine:

```text
exact reflection user prompt
  -> one or more ordinary assistant messages
  -> optional, repeatable block:
       auto=true compaction user marker
       -> linked assistant summary (summary=true, mode=compaction)
       -> fixed synthetic continuation user marker
       -> linked ordinary assistant message
```

Both pinned `overflow=false` and `overflow=true` continuation texts are
supported and tied to the compaction marker.  Arbitrary extra user turns,
near-miss prompts, malformed metadata, missing messages, wrong ordering, and
wrong parent linkage remain unscoreable.

Validation before publication:

- real E3 `v1@8` raw solve/full exports re-converted successfully;
- trajectory and raw-export continuity checks both passed on that artifact;
- 224 repository tests passed;
- targeted Ruff, format, byte-code compilation, and whitespace checks passed.

After submission, local auditor commits `7a20508` and `aece200` hardened the
composition audit without changing the packaged `v1@9` runtime.  The auditor
now reopens every delivered reflection prompt, solve/full ATIF trajectory, and
solve/full raw OpenCode export; reruns the pinned strict continuity validators;
and requires every session result to match `self_reflection_result.json`.
It also byte-binds the audit copies to the agent's canonical trajectories, raw
full export, and solve/reflection streams; validates all raw message/part IDs,
session IDs, and parent links; and compares the full canonical/raw role,
normalized-message, and compaction-control spine.

The integration fixtures cover accepted repeated automatic compaction with
both overflow modes, arbitrary extra user turns, compaction near-misses,
one-sided control evidence, empty solve histories, divergent message content,
inner session/part/parent tampering, copy tampering, and result-session
mismatch.  The resulting repository suite has 245 passing tests, with targeted
Ruff, format, byte-code compilation, and whitespace checks also passing.

The final artifact audit exposed two verifier-contract mistakes in the local
auditor, not in the immutable runtime results:

- E5 and E6 correctly emitted the four files consumed by
  `VerifierAdapter`, with `reward.txt` as the canonical reward, but no optional
  `reward.json`.  The auditor had incorrectly required the optional file.
- E2-LS4-T4 had canonical reward `1.0` while its rubric-derived normalized
  score was `99.99 / 100`.  The runtime intentionally records those two values
  from `reward.txt` and `score_report.json` respectively, but the auditor had
  incorrectly required both record fields to equal the canonical reward.

The corrected auditor requires and validates the canonical four-file bundle,
treats `reward.json` as an optional Harbor cross-check, independently binds the
record reward and normalized score to their actual sources, and byte-compares
each reflection's official-verifier snapshot to the trial verifier bundle.
Six focused regression tests, including positive variants for both real
contracts and fail-closed tamper cases, passed.  The corrected auditor then
passed the real 180-task composition with zero findings.

This remains a structural integrity check rather than a semantic or causal
quality judgment.  It also assumes the auditor's continuity implementation is
kept aligned with the benchmark revision being audited; the final report must
record both revisions explicitly.

## Canonical jobs

Every submission response and subsequent job read was checked for
`group_id=null`, namespace `megaflow-benchmark-dev`, attempt `0`, split
`v1@9`, and the exact Agent-Hub revision above.

| Environment | AP job | Idempotency key |
| --- | --- | --- |
| E1 | `ap-skillevolbench-65b6599321404bc0-o4` | `70880d21-cc89-4cba-abf8-7a0d65e2b44d` |
| E2 | `ap-skillevolbench-fbe4d4fb2d314c65-o4` | `8ad194e9-2108-4c16-b4bf-84eaa5e9a0bc` |
| E3 | `ap-skillevolbench-eab671a841b043e0-o4` | `bdb40e8b-b361-4f00-90d2-768fb3dbb20a` |
| E4 | `ap-skillevolbench-9bd3d28f6d6a400c-o4` | `bd027c5c-2135-4729-89d4-38f0a58de4a8` |
| E5 | `ap-skillevolbench-ef4fedf522e342be-o4` | `c181e2be-d8b0-4cd1-928c-9e5f264ab1ed` |
| E6 | `ap-skillevolbench-a1391fb199ff47cb-o4` | `2facdf96-ffdb-40f0-b20a-d8b334d9dc17` |

Submission evidence:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/
  standalone-v1-9-submission.json
```

## Retry and acceptance policy

- A protocol or deterministic implementation failure requires a new immutable
  benchmark revision and fresh runs; it is not repaired by selecting a lucky
  retry.
- A solve-phase model/runtime timeout may receive at most one unchanged
  standalone retry.  The failed attempt remains in diagnostics and the final
  report must label retry-selection bias.  A repeated timeout stops automatic
  recovery and requires an explicitly different timeout setting/revision.
- Every terminal job is exported with events and independently paginated
  platform logs, then scanned before composition.  `Succeeded` alone is never
  acceptance evidence.
- Composition requires one complete, scoreable `v1@9` result for each of
  E1-E6, 180 verifier-backed primary trials, 90 terminal same-session
  reflections, exact ordering/freeze boundaries, provenance and sanitizer
  integrity, and a recomputed aggregate.
- Manual review covers every failure-to-success and success-to-failure
  transition, rejected/no-op reflection, applied-but-not-retrieved skill, and
  final generated `SKILL.md`.

## Final acceptance

All six jobs completed on attempt zero and were exported with events and
independently paginated platform logs.  Every per-job safety scan passed.  The
six standalone exports were copied into a self-contained local composition;
no AP `artifacts.json` download-link metadata was copied.

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/
  standalone-v1-9-exports/
  standalone-full-v1-9-20260721/
  standalone-full-v1-9-20260721-audit-after-verifier-contract-fix.json
  standalone-full-v1-9-20260721-audit-before-verifier-contract-fix.json
  standalone-full-v1-9-20260721-skill-utility.json
```

The accepted strict audit reports:

| Check | Result |
| --- | ---: |
| Environments | 6/6 |
| Verifier-backed primary trials | 180/180 |
| Replay trials | 0 |
| Terminal reflections | 90/90 |
| Same-session reflections | 90/90 |
| Reflection-to-next-input chains | 90/90 |
| Group post-process recomputation | passed |
| Audit findings | 0 |

The aggregate evaluation score is `0.37777777777777777`; this is a model
result, not an integration failure.  Per-environment evaluation success rates
are E1 `0.4667`, E2 `0.4667`, E3 `0.2667`, E4 `0.4667`, E5 `0.4667`, and E6
`0.1333` (rounded to four decimals).

## Skill-utility evidence

The read-only utility report linked every learning reflection to the next
different input:

| Evidence | Count |
| --- | ---: |
| Completed reflections / rejected reflections | 77 / 13 |
| Preserved and applied candidates | 77 |
| Applied patches with a version record | 77 |
| Applied patches retrieved on the next input | 77 |
| Applied patches listed in `skills_actually_used` next | 70 |
| Fail-to-success transitions | 18 |
| Fail-to-fail transitions | 31 |
| Success-to-success transitions | 25 |
| Success-to-fail transitions | 16 |

Among the 77 applied-patch chains, the transition counts are 15
fail-to-success, 27 fail-to-fail, 20 success-to-success, and 15
success-to-fail.  These are observational outcomes on different next inputs.
They prove that skill state, retrieval, trajectory-use evidence, and verifier
outcomes can be measured end to end; they do not prove that a generated skill
caused the next outcome.  A matched no-reflection or retrieval-ablation arm is
still required for that causal claim.

The full manual skill and trajectory review, including exact candidate,
`SKILL.md`, and next-solve paths, is in
[ap_full_standalone_v1_9_quality_review.md](ap_full_standalone_v1_9_quality_review.md).

Accepted self-contained result root:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/
  standalone-full-v1-9-20260721/
```

Transition counts are observational.  Different next inputs are enforced, but
causal claims still require a matched no-reflection/no-retrieval control.
