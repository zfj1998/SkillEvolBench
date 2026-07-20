# AP T1-T6 family smoke report (`v1@7`)

Date: 2026-07-21 UTC

## Verdict

The AP integration can execute a complete ordered SkillEvolBench family:
T1 through T6 ran sequentially in one AP job, all six verifiers ran, the
learning library was updated after T1-T3, the library was frozen before T4,
and all solve/reflection trajectories and verifier artifacts were downloaded.
The infrastructure and artifact-integrity audit passed.

This run does **not** show that the generated skill guarantees success on a
different input. Official strict results were 3/3 on learning tasks and 0/3 on
evaluation tasks, but a contract-level audit found implementation-coupled
false negatives in T4, T5, and T6. There is also no matched no-reflection
control, so observed transitions are not causal evidence for skill benefit or
harm.

This is an explicit non-canonical `family_smoke`, not a canonical 30-task
environment episode. It proves the full T1-T6 state transition works on AP,
but does not close the canonical one-environment or six-environment gates.

## Exact run

| Field | Value |
| --- | --- |
| AP job | `ap-skillevolbench-8199e9ce930845fb-o4` |
| AP state | `Succeeded` |
| AP cluster / template | `benchmark-dev` / `skillevolbench` |
| Instance / family | `E1` / `E1-LS1` |
| Setting | `selfgen_in_session_always` |
| Dataset | `skillevolbench/skillevolbench`, split `v1@7` |
| SkillEvolBench runtime revision | `a0972c3b98f724e6b89e35ac974c142368a0c6d0` |
| Agent-Hub revision | `1e10fc0cf557d1c74e3b6dda13f4ac6001c225ad` |
| Agent | OpenCode `1.18.3` |
| Model | `serve-3.8-maxp-cpt-s1-0715-fable-1ep` |
| Created / finished | `2026-07-21T01:19:41.224` / `2026-07-21T01:53:08.907` |
| AP wall time | 2007.683 seconds (about 33.5 minutes) |
| Six-trial episode time | about 26 minutes 34 seconds |

The immutable `v1@7` package was built twice from the pinned benchmark
revision. All 13 release files were byte-identical, uploaded without
overwriting existing objects, and verified by remote size and ETag/MD5. The
release-manifest SHA-256 is
`744c2f051441ac000c75a7ba752aa0452feb84bba01cee912ef7adbf35b06c06`.
AP discovery returned exactly `E1` through `E6`.

## Protocol that actually ran

```text
T1 solve -> verifier -> resume the same session -> reflect/update skill
T2 solve with shared skill -> verifier -> same-session reflection candidate
T3 solve with shared skill -> verifier -> same-session reflection/update
                              |
                              +-> freeze environment skill library
T4 solve with frozen library -> verifier only
T5 solve with frozen library -> verifier only
T6 solve with frozen library -> verifier only
```

“Same session” is scoped to one task's solve plus reflection. T1, T2, and T3
use three separate OpenCode sessions, while sharing the same persistent
environment skill library. For every learning task, the audit proved that the
solve and reflection session IDs match, the solve trajectory/session export is
a strict prefix of the full export, the container is unchanged, and reflection
does not mutate `/root/task`.

## Per-task result

| Task | Role | Reward | Public | Hidden | Process | Official strict result | Reflection |
| --- | --- | ---: | ---: | ---: | ---: | --- | --- |
| T1 | canonical / learning | 1.00 | 5/5 | 8/8 | 5/5 | pass | completed; created skill |
| T2 | enriched / learning | 1.00 | 4/4 | 11/11 | 5/5 | pass | rejected by host |
| T3 | variant / learning | 1.00 | 3/3 | 7/7 | 3/3 | pass | completed; revised skill |
| T4 | context-shift / evaluation | 0.35 | 3/4 | 0/6 | 2/5 | fail | disabled; library frozen |
| T5 | adversarial / evaluation | 0.90 | 5/5 | 10/10 | 1/2 | fail | disabled; library frozen |
| T6 | composition / evaluation | 0.75 | 4/4 | 6/6 | 3/5 | fail | disabled; library frozen |

Official metrics therefore report `learning_sr=1.0`, `evaluation_sr=0.0`, and
`task_score=0.0`. The zero task score is intentional because a family smoke is
`completed_noncanonical`, `canonical=false`, and `scoreable=false`.

### What the three evaluation failures mean

- **T4 is dominated by verifier coupling.** The model fixed the underlying app
  while preserving backward compatibility; the three existing `ci_tests/`
  pass on the delivered artifact. Its real FastAPI webhook returns the expected
  statuses for valid, invalid, and missing signatures, invalid JSON and missing
  fields, and stores a verified event. The six hidden tests never call that
  route: they require an undocumented synchronous helper named
  `handle_webhook_request`. The failed public test requires user routes to
  return a bare list although the starter route preserves a `{"users": ...}`
  envelope. Three process checks require the golden implementation strategy of
  editing test files, even though the model made those tests pass by fixing the
  app. These checks do not faithfully isolate the written contract.
- **T5 is behaviorally correct but strictly rejected.** All 15 functional tests
  passed. The model repaired the ordering mismatch by rebuilding `_RATE_VECTOR`
  in the same sorted order as `_REGION_TO_CODE`. The sole failed process check
  searches for the literal `_RATE_VECTOR[code]` and requires that lookup to be
  removed, so it rejects this equivalent general fix.
- **T6 is behaviorally correct but strictly rejected.** All 10 functional tests
  passed. The model encoded credentials with `quote(..., safe='')`; the process
  verifier requires the literal `quote_plus`. The two encodings differ for
  spaces but both satisfy the tested DSN contract, and every hidden failure,
  concurrency, URL, and error-propagation test passed. One aggregate process
  check fails as a consequence of the same literal requirement.

For capability analysis, retain the official strict result, official
outcome-test result, and independent contract audit separately. The official
evaluation result is 0/3; the official outcome-only view is 2/3; the
contract-level audit judges all three evaluation implementations functional.
Do not silently replace the benchmark's primary metric with an audited metric,
but do not treat these implementation-specific failures as clean model-capacity
evidence either.

## Generated skill and reflection behavior

The final library contains one active skill,
`systematic-error-diagnosis`, created from T1 and revised after T3. It covers:

- diagnosing loud concurrency failures from the violated invariant;
- choosing single-flight or narrowly scoped synchronization instead of hiding
  an exception or globally serializing slow work;
- diagnosing silent success that flattens an upstream failure into a healthy
  zero/default value;
- preserving failure signals and testing both the forced-failure and healthy
  paths.

This is substantive reusable content rather than a copied task solution: the
final library contains no task IDs, hidden-test text, concrete endpoints,
credentials, or literal patches. Its main weaknesses are:

- the routing description is broad enough to match almost any existing-service
  bug, including T4 and T5 where its two core patterns were only loosely related;
- the T3 revision retains mild public-task-specific examples such as
  `Promise.allSettled`, `recoverable_failures`, and `failure_log`;
- `scripts/repro_concurrency.py` is a scaffold, not a strong test: it checks
  status codes but not response invariants or single-flight computation count,
  and its parallelism check can pass even if every request returns 500.

T2 produced a useful revision about fail-open security, but the host correctly
rejected it. The candidate's YAML frontmatter used an unquoted description
containing `Two recurring classes: ...`; PyYAML raises
`mapping values are not allowed here` at line 2, column 234. The model had
validated JSON and used regexes to check that frontmatter keys existed, but did
not parse the YAML. Consequently, the final skill lost the T2 lesson about
closing every fail-open layer. Reflection status is therefore two completed and
one rejected, with a valid-output rate of 2/3.

The replay records and injection contexts agree that T2-T6 all retrieved and
claimed actual use of `systematic-error-diagnosis`; their trajectories also
explicitly load and discuss it. This proves exposure and observable use, not
causal benefit. T4 still received an official strict failure, and there is no
paired run without the skill.

One bookkeeping inconsistency remains: the final library `manifest.yaml` keeps
its `retrieval_count`, `use_count`, `success_count`, and `failure_count` at
zero, while the replay-derived full report correctly records five uses and a
0.6 strict failure rate. Use replay records plus trajectory evidence for this
run; do not infer non-use from those stale manifest counters.

## Artifact completeness and integrity

The export root is:

```text
/cpfs01/user/zhangfengji.zfj/workspace/skillevolbench_ap_results/
  ap-skillevolbench-8199e9ce930845fb-o4
```

It is about 112 MiB and contains 1,479 files when hidden Git-library files are
included. The benchmark payload contains one run directory, six primary replay
records, six canonical solve trajectories, three full same-session reflection
audits, every verifier report/reward, the final Git-backed skill library,
lifecycle/patch/retrieval events, model probes, preflight output, and final
metrics.

The sanitizer changed 45 files. `sanitization_manifest.json` validates every
runtime-to-delivered SHA-256 and size pair; the four changed T2 audit files are
therefore explainable instead of appearing corrupted. The audit also proved:

- exactly one freeze/unfreeze boundary, strictly between T3 and T4;
- the T4-T6 pre/post library hashes and delivered Git tree equal the frozen
  tree;
- no learning patch was generated during evaluation;
- ordinary source literal `LEGACY_EMPTY_REGION = ""` was not corrupted;
- no live AP/model/OSS credential, ephemeral no-auth sentinel, signed URL, or
  private key exists in the benchmark output tree.

The stock AP CLI `0.1.16` log exporter requested 1,000 entries per page while
the service accepts at most 500, leaving one-byte placeholder log files. A
read-only pagination export was then run at 500 entries per page and verified
by a second fetch: 3,273 platform log entries are now complete, including
3,012 `main` entries over seven pages. `logs/pagination_manifest.json` records
every page boundary, byte count, and SHA-256. This AP CLI issue did not affect
`result.tgz` or any benchmark trajectory.

The top-level AP transport metadata is not part of the sanitized benchmark
payload and may contain an expiring artifact URL. Do not copy or publish that
metadata; use `artifacts/output/` for benchmark handoff.

## What this establishes, and what remains

Established:

- AP can run the explicit T1-T6 family protocol with shared state and a freeze
  boundary;
- the task agent can solve and reflect in one verifiably continuous session;
- a candidate skill can be host-validated, applied, revised, frozen, retrieved,
  and exposed on different inputs;
- the downloaded evidence is complete and cryptographically auditable.

Not established:

- that reflection caused any later success or failure;
- that a failure-derived reflection helps the next different input, because
  all three learning tasks happened to pass in this run;
- that the model reliably emits valid skill candidates (one of three was lost
  to YAML formatting);
- reliable capability scores from this family until its implementation-coupled
  verifiers are corrected;
- consistent per-skill evidence counters in the final library manifest;
- canonical 30-task environment completion or six-environment aggregation.

For the user's target hypothesis, the next scientific experiment should pair
this setting with the same family/order/model under a no-reflection control,
repeat across several families and seeds, and compare strict, outcome-only, and
contract-audited T4-T6 results. The affected family verifier should be corrected
before using it for a headline causal metric. That estimates benefit and harm
rates on different inputs; it cannot honestly provide a deterministic
“guarantee next success/failure.”

Operationally, the next platform gate is one complete 30-primary-task
environment (`--scope environment`), followed by the six-environment group.
