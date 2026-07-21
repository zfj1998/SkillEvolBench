# SkillEvolBench v1@9 skill and trajectory quality review

Last updated: 2026-07-21 UTC

## Scope

This review uses the accepted self-contained `v1@9` composition at:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/
```

The machine-readable evidence chain is:

```text
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721-skill-utility.json
```

The strict structural audit passed with zero findings.  This document asks a
different question: did the model produce reusable skills, retrieve them on a
different next input, visibly use them, and then succeed or fail?

## Evidence completeness

The composition contains:

| Artifact | Count |
| --- | ---: |
| Primary replay-store records | 180 |
| Canonical agent solve trajectories | 180 |
| Canonical agent full trajectories | 180 |
| Learning-task solve/full audit trajectories | 90 / 90 |
| Learning-task solve/full raw session exports | 90 / 90 |
| Canonical `reward.txt` verifier signals | 180 |
| Preserved valid reflection candidates | 77 |
| Final active `SKILL.md` files | 35 |

Every learning reflection was verified to resume the exact solve session.  A
candidate was applied only after the official verifier and before a later
different input.  T4-T6 ran with the library frozen.

## Aggregate behavior

Across the 90 reflection-to-next-input chains:

| Reflection result | F->S | F->F | S->S | S->F | Total |
| --- | ---: | ---: | ---: | ---: | ---: |
| Completed and applied | 15 | 27 | 20 | 15 | 77 |
| Rejected, no patch applied | 3 | 4 | 5 | 1 | 13 |
| All | 18 | 31 | 25 | 16 | 90 |

All 77 applied patches have a recorded skill version and were retrieved for
the next different input; 70 were listed in `skills_actually_used`.  Manual
trajectory review of the 15 applied fail-to-success chains found explicit
skill use in 14.  In the remaining chain, E4-LS2-T3 to T4, the model retrieved
and read the skill but explicitly judged it inapplicable and solved from
scratch.

These numbers are observational, not causal.  Three rejected/no-patch chains
also changed from failure to success.  Raw recovery was 15/42 after a completed
reflection versus 3/7 after rejection, while raw regression was 15/35 versus
1/6.  The groups are tiny and not randomized, and each next tier changes the
input and often the difficulty.  These ratios therefore must not be read as a
treatment effect.

## Manual review of applied fail-to-success skills

The 15 applied fail-to-success candidates were scored on five 0-2 dimensions:
generality, family relevance, avoidance of literal answer copying,
syntax/integrity, and downstream reuse.

- 4/15 were clean mechanism-level reusable skills (10/10).
- 9/15 contained a sound method but also verifier-shaped placement, static
  grep, or literal-output guidance (9/10).
- 2/15 were weak or ambiguous transfers (7/10).
- Total: 135/150; median 9/10.
- The weakest dimension was avoiding answer/verifier-specific detail: 18/30.

The final `SKILL.md` can contain later revisions.  For the exact content that
caused a particular source-to-next edge, use that source task's
`self_reflection_patch.json` and its recorded git commit.

### Strong example 1: fail-closed error propagation

`E1-LS1-T2` failed at reward `0.85`, reflected into
`fail-open-auth-bypass`, and `E1-LS1-T3` then passed at reward `1.0`.  The
source concerned bad credentials; the next input concerned rejected Promise
settlements being flattened into healthy-looking zero baselines.  The next
trajectory explicitly extracted the general fail-closed pattern, preserved
failure state at the fault site, and kept the success contract intact.

```text
candidate:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS1-T2__a4r6yVf/self-reflection-audit/self_reflection_patch.json
final skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/library/E1/active/fail-open-auth-bypass/SKILL.md
next solve trajectory:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS1-T3__C3QwTFs/agent/trajectory.solve.json
```

### Strong example 2: pagination invariants across API styles

`E2-LS3-T1` failed at reward `0.9167` on offset pagination, generated
`pagination-complete-retrieval`, and `E2-LS3-T2` passed on a different opaque
cursor API with variable page sizes and duplicated boundary rows.  The next
trajectory read the skill, preserved the cursor byte-for-byte, removed a fixed
limit, and deduplicated 84 raw rows into 80 ordered unique rows.

```text
candidate:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-fbe4d4fb2d314c65-o4/artifacts/output/runs/ap__selfgen_in_session_always__E2__20260720_232523/harbor-job/ap__selfgen_in_session_always__E2__20260720_232523/E2-LS3-T1__fL4gbfY/self-reflection-audit/self_reflection_patch.json
final skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-fbe4d4fb2d314c65-o4/artifacts/output/runs/ap__selfgen_in_session_always__E2__20260720_232523/library/E2/active/pagination-complete-retrieval/SKILL.md
next solve trajectory:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-fbe4d4fb2d314c65-o4/artifacts/output/runs/ap__selfgen_in_session_always__E2__20260720_232523/harbor-job/ap__selfgen_in_session_always__E2__20260720_232523/E2-LS3-T2__mKhoUhM/agent/trajectory.solve.json
```

### Strong example 3: schema normalization across dirty exports

`E3-LS1-T1` failed at reward `0.9167` because typed-field normalization was
missing, generated `schema-inspection-before-query`, and `E3-LS1-T2` passed on
a different DACH revenue export.  The next trajectory lists and loads the
skill, identifies UTF-8 BOM and zero-width-space failure modes, implements the
repair in the schema/coercion layer, and verifies that all 800 rows are kept.

```text
candidate:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-eab671a841b043e0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E3__20260720_232523/harbor-job/ap__selfgen_in_session_always__E3__20260720_232523/E3-LS1-T1__DmefL39/self-reflection-audit/self_reflection_patch.json
final skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-eab671a841b043e0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E3__20260720_232523/library/E3/active/schema-inspection-before-query/SKILL.md
next solve trajectory:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-eab671a841b043e0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E3__20260720_232523/harbor-job/ap__selfgen_in_session_always__E3__20260720_232523/E3-LS1-T2__nswbB8g/agent/trajectory.solve.json
```

## Quality problems visible in the run

Many skills are useful at the mechanism level but contaminated with benchmark
implementation details.  Examples include instructions to make code
"statically visible", put a marker in every named module because a process
check greps per file, or use exact literal words.  The clearest overfit case is
`E6-LS2-T3`: its skill says the verifier greps literal word forms and advises
using `phased`, spelling out `six`, and matching exact substrings.  It precedes
a fail-to-success edge, but is much closer to a verifier cheat sheet than a
general communication skill.

The benchmark prompt also requires the agent to inspect the skill library.
Consequently, retrieval and use here demonstrate that the plumbing works, not
how often an unconstrained agent would voluntarily reuse a skill.  Retrieval
scores can be low or negative, so `skills_actually_used` plus the solve
trajectory is stronger evidence than retrieval alone.

## Success-to-failure and non-use review

All 15 applied success-to-failure chains started at reward `1.0`; their next
rewards ranged from `0.35` to `0.9167`, with mean `0.7653`.  The new patch was
explicitly used in 13/15 next trajectories.  The next-input roles were six
context shifts, five enriched tasks, and four variants.  This distribution is
another reason not to interpret regression as a causal harm from the skill.

A representative used-but-regressed chain is E5-LS1-T2 to T3 (`1.0` to
`0.625`).  The model loaded and cited `multi-source-search-filter`, but wrote
its logic into a temporary one-off script and generated the output once.  It
did not repair the canonical `market_pipeline.py` and `authority_policy.py`
entrypoints that the official verifier reran, so three of eight checks failed.
That is an agent execution-discipline failure, not missing AP state or
artifacts.

```text
candidate:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-ef4fedf522e342be-o4/artifacts/output/runs/ap__selfgen_in_session_always__E5__20260720_232523/harbor-job/ap__selfgen_in_session_always__E5__20260720_232523/E5-LS1-T2__yR3dmfZ/self-reflection-audit/self_reflection_patch.json
final skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-ef4fedf522e342be-o4/artifacts/output/runs/ap__selfgen_in_session_always__E5__20260720_232523/library/E5/active/multi-source-search-filter/SKILL.md
next solve trajectory:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-ef4fedf522e342be-o4/artifacts/output/runs/ap__selfgen_in_session_always__E5__20260720_232523/harbor-job/ap__selfgen_in_session_always__E5__20260720_232523/E5-LS1-T3__YCqDCyw/agent/trajectory.solve.json
```

Seven applied patches were retrieved but not listed in
`skills_actually_used`: five occurred on entry to a context-shift input, four
next tasks still passed, and three failed.  Four trajectories chose another
skill and three used no skill.  The clearest case, E1-LS1-T3 to T4, reasonably
declined a new skill about errors being coerced to healthy defaults because
the context-shift task concerned webhook/HMAC validation.  It selected an
older auth-related skill instead.  Its `0.35` failure came from concrete hidden
contract misses, not a broken retrieval or injection path.

```text
candidate:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS1-T3__C3QwTFs/self-reflection-audit/self_reflection_patch.json
final skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/library/E1/active/fail-open-coerced-default/SKILL.md
next solve trajectory:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS1-T4__gjzJqWU/agent/trajectory.solve.json
```

## Why 13 reflections were rejected

Eleven rejected candidates had invalid YAML frontmatter.  The model wrote a
long unquoted plain-scalar `description:` containing `: `, which strict
`yaml.safe_load` correctly rejected with `mapping values are not allowed
here`.  Its own claimed frontmatter check was only a shallow JSON/delimiter
check.  The other two reflections exhausted a 16,384-token completion entirely
in reasoning and produced no candidate-file tool event.  The evaluator
correctly rejected all 13 cases and preserved the raw reflection evidence.

For example, E1-LS2-T2 attempted to revise
`dependency-conflict-resolution`; the unquoted description contained a
dependency error followed by a colon.  There is intentionally no normalized
candidate file, but the raw reflection stream preserves the attempted content.

```text
expected candidate, correctly absent:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS2-T2__hEaak8P/self-reflection-audit/self_reflection_patch.json
raw reflection stream:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/harbor-job/ap__selfgen_in_session_always__E1__20260720_232525/E1-LS2-T2__hEaak8P/self-reflection-audit/opencode.reflection.jsonl
final existing skill:
/mnt/workspace/zhangfengji.zfj/skillevolbench_ap_results/standalone-full-v1-9-20260721/jobs/ap-skillevolbench-65b6599321404bc0-o4/artifacts/output/runs/ap__selfgen_in_session_always__E1__20260720_232525/library/E1/active/dependency-conflict-resolution/SKILL.md
```

Two direct benchmark improvements follow from these model failures without
changing the scientific state boundary: require YAML block scalars or quoted
descriptions and validate with the same strict parser before submission; and
ask the reflection turn to write a minimal valid candidate before expanding
its reasoning, so a long completion cannot consume the whole output budget
without producing evidence.

## Conclusion for the target research question

This integration can reliably measure all of the required observables:

1. solve a task;
2. run the official verifier;
3. reflect in the same agent session;
4. validate and apply a skill candidate;
5. expose that state to a different next input;
6. record retrieval, explicit trajectory use, and the next verifier outcome;
7. count both failure-to-success and success-to-failure transitions.

The run also contains convincing individual examples of useful skill transfer.
It does not show that reflection guarantees success or causes failure.  The
next scientific run should hold the task sequence fixed and compare at least
`selfgen_in_session_always` against a matched no-apply or retrieval-ablation
arm.  Report exact consumed skill versions and stratify by whether the next
trajectory actually used the skill.
