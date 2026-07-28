# Task-contract and verifier quality audit

This draft collects benchmark-task changes discovered while studying whether
skills learned on T1--T3 help on changed T4--T6 inputs. It intentionally excludes
the experiment platform, model harness, and reporting code so the task contracts
can be reviewed independently.

## Why this audit was needed

A model failure is not, by itself, evidence that a task is defective. We changed
a task only after reproducing at least one of the following:

1. the instruction and verifier required different behavior;
2. the fixture made the required result impossible;
3. the verifier selected one undeclared answer among semantically equivalent
   outputs;
4. a process test inspected private source spelling or file layout instead of
   observable behavior; or
5. the official solution, fixture, and verifier disagreed.

The main scientific concern is attribution. If a correct implementation can be
rejected because it does not contain a hidden token, then a later "skill
improvement" may only show that the model memorized verifier wording. It does not
necessarily show transferable task knowledge.

## What changed

Across the 90 held-out T4--T6 tasks:

- 27 tasks received an outcome or task-contract repair;
- 27 additional tasks received a process-verifier-only rewrite;
- 36 tasks were left unchanged;
- 2 scheduling instances were replaced instead of patched; and
- all 30 skill-family capability targets were retained.

### Outcome and contract repairs

| Task | Reproduced problem | Proposed repair |
| --- | --- | --- |
| E1-LS4-T5 | Monkeypatching one database binding missed starter-style imported aliases; source scans required particular files/tokens. | Patch both live bindings and judge observable HTTP failure/recovery behavior. |
| E1-LS5-T5 | A broad regex rejected safe parameterized SQL after scanning non-SQL arguments and surrounding source. | Inspect the SQL argument structurally and reject actual interpolation. |
| E2-LS1-T6 | A public test required three results although all four fixtures were valid; hidden checks searched source strings. | Align the expected output with four valid inputs and test validation, normalization, fallback, and call order at runtime. |
| E3-LS2-T6 | Full-dictionary equality rejected additional audit fields allowed by the instruction. | Compare the required semantic projection. |
| E3-LS3-T6 | Category totals were compared as an array with an undeclared order. | Compare by semantic category key. |
| E3-LS4-T6 | Exact nested-dictionary equality rejected permitted null-audit information. | Require the expected recursive subset while allowing extra audit fields. |
| E3-LS5-T5 | A permissive parser interpreted malformed `1,2,3` as `123`, producing 706 instead of the generator-consistent 700. | Use documented strict numeric syntax and align the solution and expected count to 700. |
| E4-LS1-T5 | Instruction and verifier named different output locations. | Use the instruction-defined path consistently. |
| E4-LS2-T6 | Formatted DOCX values such as `$125,000` failed a raw-token check; helper modules were ignored. | Parse formatted numeric surfaces and inspect the executed pipeline plus helpers. |
| E4-LS3-T5 | The task allowed `UNKNOWN`, `MISSING`, empty, or null, but the verifier accepted a different narrow set. | Accept the markers promised by the instruction while rejecting hallucinated values. |
| E4-LS4-T5 | Correct page-reference semantics failed a fixed-tense wording regex. | Check page numbers and the correction relationship semantically. |
| E4-LS4-T6 | Correct policy changes failed on en dashes or `per month` wording. | Normalize equivalent numeric, time-range, and wording surfaces. |
| E5-LS1-T4 | A report saying a noisy semiconductor source was excluded failed a generic banned-word check. | Ban actual noise IDs/titles in selected evidence, not topical words in audit explanations. |
| E5-LS3-T4 | The required `valid` / `misrepresented` / `fake` taxonomy was hidden. | Publish the label definitions. |
| E5-LS3-T5 | The hidden taxonomy treated a supported source as invalid and required labels not derivable from the prompt. | Publish the taxonomy and align authenticity/support ground truth. |
| E5-LS3-T6 | A valid source was excluded from the full-audit contract. | Include S02 as valid and require a complete evidence-grounded audit. |
| E5-LS4-T6 | Correct concepts failed narrow lexical checks such as `validation` vs `validated`. | Use word-family and theme groups. |
| E6-LS1-T4 | A reply was required for a message with no visible recipient-directed request. | Make the confirmation request visible in all synchronized mail sources and publish the response-vs-draft contract. |
| E6-LS1-T5 | Hidden urgency labels conflicted with the visible P1 definition and mixed impact with tone. | Publish P0--P3 definitions and ground labels in business-impact evidence. |
| E6-LS1-T6 | Expected P0 set, reply facts, and exact lexical context were unpublished. | Publish the priority/reply contract and visible context; accept semantic alternative groups rather than one reference token. |
| E6-LS2-T5 | A contextual rationale failed only because it omitted the literal word `timeline`. | Check the required facts and friendly alternatives semantically. |
| E6-LS2-T6 | Correct routing/refusal failed fixed phrases such as `not promise`. | Check recipient, CC, evidence, and commitment semantics. |
| E6-LS3-T5 | Hidden action IDs and a speaker-name rule contradicted allowed team/role assignees. | Align by source message and accept instruction-permitted assignee forms. |
| E6-LS3-T6 | Raw ordering and unpublished IDs rejected source-aligned action extraction. | Align by source, then check assignee, deadline, status, and follow-up semantics. |
| E6-LS4-T5 | Several slots were equally feasible, but one hidden ID and first-item tie-break were required. | Replace the instance with stable slot IDs and a published earliest-UTC tie-break. |
| E6-LS4-T6 | The original four-person fixture had no positive-length common working-hours intersection. | Replace it with per-meeting attendee sets, feasible windows, and a published lexicographic objective. |
| E6-LS5-T5 | Assignee `team` was instruction-valid but rejected; process tests searched variable names and an unrelated phrase. | Accept permitted assignees and test question-vs-action behavior. |

### Process-verifier-only rewrites

These tasks had no reproduced outcome-contract defect, but a process check
required source words, variable names, specific helper layout, or other
implementation details that were not part of the task:

```text
E1-LS1-T5  E1-LS1-T6
E2-LS1-T5  E2-LS2-T5  E2-LS2-T6  E2-LS3-T4  E2-LS3-T5
E2-LS3-T6  E2-LS4-T6  E2-LS5-T4  E2-LS5-T5  E2-LS5-T6
E3-LS1-T6  E3-LS4-T5  E3-LS5-T4  E3-LS5-T6
E4-LS2-T4  E4-LS5-T4  E4-LS5-T6
E5-LS1-T5  E5-LS2-T4  E5-LS2-T5  E5-LS2-T6
E6-LS1-T4  E6-LS2-T4  E6-LS3-T4  E6-LS4-T4
```

The replacement tests exercise observable outcomes such as retry behavior,
fallback order, pagination, deterministic output, validation, and reconciliation.
Removing a lexical check does not mean removing process evaluation.

## Cross-task consistency checks

`tests/test_v1_1_verifier_quality.py` prevents the most important classes of
regression:

- all E6 process verifiers remain nontrivial but do not require unpublished
  source markers;
- all six inbox-triage tasks publish the same P0--P3 boundary;
- synchronized JSON, mbox, and raw EML fixtures contain the same decisive facts;
- concrete same-day blockers receive labels consistent with the published
  policy;
- reply-drafting checks accept contextual semantic alternatives while still
  rejecting generic replies; and
- the two replacement scheduling instances remain feasible and deterministic.

## Validation performed

- Every checked-in reference solution was run in its real task container:
  **90/90 held-out T4--T6 tasks passed strict verification**.
- A fresh live-agent family run covered T1--T6 on the final fixtures:
  **6/6 tasks passed strict verification**.
- `python scripts/validate_assets.py` passed for **30 families / 180 tasks**.
- The focused upstream test suite passed: **15 tests**.

The reference audit establishes internal solvability, not that every task is
perfect or that a particular model should pass. Live runs remain useful because
they can expose semantically valid outputs that the reference solution does not
exercise.

## Questions for maintainers

This is intentionally a draft/RFC-sized change. The main review questions are:

1. Are the published task policies faithful to the intended latent skills?
2. Should process verifiers constrain implementation structure at all, or only
   observable behavior?
3. For equivalent valid outputs, should the verifier accept a semantic set or
   should the task publish one deterministic tie-break?
4. Do the replacement E6 scheduling instances preserve the intended difficulty?
5. Would maintainers prefer this patch split by environment or by defect class
   before merge?
