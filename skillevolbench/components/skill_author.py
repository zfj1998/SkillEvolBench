"""SkillAuthor -- LLM client for skill creation + revision (Part 6 §6.4).

Three call sites:

* :meth:`induce_skill`     -- T1 self-gen induction from execution trace.
* :meth:`zero_shot_create` -- Self-Gen-Zero-Shot pre-execution drafting.
* :meth:`propose`          -- T2/T3 revision (called by Chain / Tree / RGPE).

The class accepts an injectable LLM ``call_fn(prompt: str) -> str`` so that:

* tests use a deterministic stub
* production wires :class:`LiteLLMClient` (default) which calls
  ``litellm.completion`` with ``response_format={"type": "json_object"}``

Each of the three methods builds a JSON-shaped prompt asking the LLM to
emit ``{summary, upsert_files, delete_paths, operation_type}`` and parses
that into a :class:`SkillPatch`. Parsing failures fall back through a
fixed chain of simpler prompts (mode -> simplified -> no-examples).
"""

from __future__ import annotations

import json
import logging
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Awaitable, Callable, Optional

from skillevolbench.schemas import (
    FeedbackLevel,
    OperationType,
    SkillManifestEntry,
    SkillPatch,
)


_LOG = logging.getLogger(__name__)


# Type alias for an LLM call. May be sync or async; SkillAuthor wraps both.
SyncCall = Callable[[str], str]
AsyncCall = Callable[[str], Awaitable[str]]


class PatchGenerationFailure(RuntimeError):
    pass


# ---------------------------------------------------------------------------
# LiteLLMClient -- production default; lazy-imports litellm
# ---------------------------------------------------------------------------


class LiteLLMClient:
    """Sync + async LLM caller backed by ``litellm.completion``."""

    def __init__(
        self,
        model: str = "anthropic/claude-opus-4-5",
        api_base: Optional[str] = None,
        api_key: Optional[str] = None,
        temperature: float = 0.2,
        max_tokens: int = 16384,
        json_mode: bool = True,
        tag: str = "llm",
    ) -> None:
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.json_mode = json_mode
        # Optional prompt/response dump. Enabled by setting env var
        # ``SEVB_DUMP_PROMPTS=<dir>`` (or ``=1`` to default to
        # ``./workspace/llm_calls/``). Each call appends one JSON line to
        # ``<dir>/<tag>.jsonl``. Off by default; cheap when on.
        self._tag = tag
        self._dump_dir: Optional[Path] = self._resolve_dump_dir()
        # Cumulative token / call counters. Read by metrics/cost.py at
        # run end to compute host-side USD via the price table.
        # Cache tokens are the cache-read kind that providers discount
        # heavily (~10x cheaper than input). litellm exposes them as
        # ``usage.cache_read_input_tokens`` (Bedrock) or
        # ``usage.prompt_tokens_details.cached_tokens`` (OpenAI).
        self._n_input_tokens: int = 0
        self._n_output_tokens: int = 0
        self._n_cache_tokens: int = 0
        self._n_calls: int = 0

    @staticmethod
    def _resolve_dump_dir() -> Optional[Path]:
        v = os.environ.get("SEVB_DUMP_PROMPTS", "").strip()
        if not v:
            return None
        if v == "1":
            v = "workspace/llm_calls"
        p = Path(v).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _dump(self, prompt: str, response: str) -> None:
        if self._dump_dir is None:
            return
        rec = {
            "ts": time.time(),
            "tag": self._tag,
            "model": self.model,
            "temperature": self.temperature,
            "prompt": prompt,
            "response": response,
        }
        (self._dump_dir / f"{self._tag}.jsonl").open("a").write(
            json.dumps(rec, ensure_ascii=False) + "\n"
        )

    def _accumulate_usage(self, resp: Any) -> None:
        """Pull token counts off ``litellm.completion``'s response.usage.

        Fields differ slightly across providers:
          - Bedrock:  usage.cache_read_input_tokens (separate)
          - OpenAI:   usage.prompt_tokens_details.cached_tokens (nested)
          - Gemini:   no cache field
        We sum what we can find; missing fields stay at 0.
        """
        usage = getattr(resp, "usage", None)
        if usage is None:
            return
        n_in = int(getattr(usage, "prompt_tokens", 0) or 0)
        n_out = int(getattr(usage, "completion_tokens", 0) or 0)
        # Cache-read tokens (the heavily-discounted ones).
        n_cache = int(getattr(usage, "cache_read_input_tokens", 0) or 0)
        if not n_cache:
            details = getattr(usage, "prompt_tokens_details", None)
            if details is not None:
                n_cache = int(getattr(details, "cached_tokens", 0) or 0)
        # Subtract cache from raw input so we don't double-count.
        # (Most providers report prompt_tokens INCLUDING cached tokens.)
        if n_cache and n_in >= n_cache:
            n_in -= n_cache
        self._n_input_tokens  += n_in
        self._n_output_tokens += n_out
        self._n_cache_tokens  += n_cache
        self._n_calls += 1

    @staticmethod
    def _configure_litellm(litellm_module: Any) -> None:
        """Apply cross-provider compatibility settings.

        - drop_params=True: silently drop params unsupported by the target
          provider (e.g. gpt-5 rejects temperature=0; gpt-5 expects
          max_completion_tokens not max_tokens).
        - num_retries=8: handle transient 5xx (Gemini ServiceUnavailable
          "high demand" 503s especially). Litellm uses exponential backoff
          internally, so 8 retries cover ~5+ minutes of wall time before
          giving up -- enough to ride out most provider-side overloads.
          Important: SkillAuthor.propose / induce_skill have NO fallback;
          a hard failure here aborts the trial. Aggressive retries
          minimise this.

        Unconditional sets (some litellm versions initialise these to None,
        which would break comparison-based guards).
        """
        litellm_module.drop_params = True
        litellm_module.num_retries = 8

    def __call__(self, prompt: str, *, system_prompt: Optional[str] = None) -> str:
        import litellm  # lazy
        self._configure_litellm(litellm)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = litellm.completion(**kwargs)
        out = resp.choices[0].message.content
        self._accumulate_usage(resp)
        # Dump records the full conversation for replay/audit.
        self._dump((system_prompt or "") + "\n---\n" + prompt, out)
        return out

    async def acall(self, prompt: str, *, system_prompt: Optional[str] = None) -> str:
        import litellm  # lazy
        self._configure_litellm(litellm)
        messages: list[dict[str, str]] = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        if self.api_base:
            kwargs["api_base"] = self.api_base
        if self.api_key:
            kwargs["api_key"] = self.api_key
        if self.json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        resp = await litellm.acompletion(**kwargs)
        out = resp.choices[0].message.content
        self._accumulate_usage(resp)
        self._dump((system_prompt or "") + "\n---\n" + prompt, out)
        return out


# ---------------------------------------------------------------------------
# SkillAuthor
# ---------------------------------------------------------------------------


class SkillAuthor:
    """LLM-backed proposer of :class:`SkillPatch` objects.

    The ``feedback_level`` constructor argument controls how rich the
    failure-feedback signal is when rendering INDUCTION and REVISION
    prompts. See ``_format_feedback`` for the per-level formatting.
    """

    def __init__(
        self,
        sync_call: Optional[SyncCall] = None,
        async_call: Optional[AsyncCall] = None,
        feedback_level: FeedbackLevel | str = FeedbackLevel.PROCESS,
    ) -> None:
        if sync_call is None and async_call is None:
            client = LiteLLMClient()
            self._sync_call: SyncCall = client.__call__
            self._async_call: AsyncCall = client.acall
        else:
            self._sync_call = sync_call or _no_sync
            self._async_call = async_call or _wrap_sync_as_async(self._sync_call)
        # Normalize: callers may pass a raw string ("process") or the enum.
        if isinstance(feedback_level, str):
            feedback_level = FeedbackLevel(feedback_level)
        self._feedback_level: FeedbackLevel = feedback_level

    # ------------------------------------------------------------------
    # LLM dispatch (sync + async) with system/user split
    # ------------------------------------------------------------------

    def _call_llm_sync(self, *, user: str, system: str) -> str:
        """Invoke the sync LLM with system + user messages.

        Falls back to a single concatenated prompt when the injected
        ``sync_call`` is an old-style stub that doesn't accept
        ``system_prompt`` (common in tests). LiteLLMClient and any new
        stubs should accept the kwarg and route system into a real
        ``role: system`` message -- which is what gives prompt-cache
        savings + better instruction adherence vs cramming everything
        into user.
        """
        try:
            return self._sync_call(user, system_prompt=system)
        except TypeError:
            return self._sync_call(system + "\n\n" + user)

    async def _call_llm_async(self, *, user: str, system: str) -> str:
        try:
            return await self._async_call(user, system_prompt=system)
        except TypeError:
            return await self._async_call(system + "\n\n" + user)

    # ------------------------------------------------------------------
    # propose -- T2 / T3 revision
    # ------------------------------------------------------------------

    def propose(
        self,
        *,
        library: Any,
        compacted: Any,
        outcome: Any,
        target_skill_ids: list[str],
        mode: str = "minimal_edit",
        suggested_target_skill_ids: Optional[list[str]] = None,
    ) -> SkillPatch:
        """``target_skill_ids`` is the FULL set of in-family skills the LLM
        is allowed to revise (parser will accept upserts under any of
        these slugs); ``suggested_target_skill_ids`` (subset) is the
        retriever's best guess, surfaced as a "← suggested" marker in
        the prompt so the LLM has a starting point but not a constraint.

        When ``suggested_target_skill_ids`` is None or empty, we treat
        all of ``target_skill_ids`` as the suggestion (legacy behaviour).
        """
        prompt_modes = self._fallback_chain(mode)
        last_error: Optional[Exception] = None
        suggested = suggested_target_skill_ids or target_skill_ids
        for attempt, current_mode in enumerate(prompt_modes, start=1):
            system, user = self._render_revision_prompt(
                mode=current_mode,
                library=library,
                compacted=compacted,
                outcome=outcome,
                target_skill_ids=target_skill_ids,
                suggested_target_skill_ids=suggested,
            )
            try:
                raw = self._call_llm_sync(user=user, system=system)
                patch = self._parse_revision_patch(
                    raw=raw,
                    target_skill_ids=target_skill_ids,
                    triggered_by_task=getattr(outcome, "task_id", "?"),
                    failure_summary=getattr(outcome, "failure_summary", ""),
                    proposing_mode=current_mode,
                    attempt_count=attempt,
                )
                return patch
            except Exception as exc:
                last_error = exc
                _LOG.warning(
                    "SkillAuthor.propose: mode=%s attempt=%d failed: %s",
                    current_mode, attempt, exc,
                )
        raise PatchGenerationFailure(
            f"All revision fallbacks failed (last={last_error!r})"
        )

    # ------------------------------------------------------------------
    # induce_skill -- T1 induction
    # ------------------------------------------------------------------

    def induce_skill(
        self,
        *,
        family_id: str,
        latent_skill_id: str,
        compacted: Any,
        outcome: Any,
    ) -> SkillPatch:
        system, user = self._render_induction_prompt(
            family_id=family_id,
            latent_skill_id=latent_skill_id,
            compacted=compacted,
            outcome=outcome,
        )
        raw = self._call_llm_sync(user=user, system=system)
        return self._parse_create_patch(
            raw=raw,
            latent_skill_id=latent_skill_id,
            triggered_by_task=getattr(outcome, "task_id", "?"),
            proposing_mode="induce_from_experience",
        )

    # ------------------------------------------------------------------
    # zero_shot_create -- async because Part 4 hook awaits it
    # ------------------------------------------------------------------

    async def zero_shot_create(
        self,
        *,
        family_id: str,
        latent_skill_id: str,
        family_meta: Any,
    ) -> str:
        """Returns the skill content (raw markdown), NOT a SkillPatch.

        The hook persists the content via ``library.create_skill(...)``;
        this method only does the LLM call.
        """
        system, user = self._render_zero_shot_prompt(
            family_id=family_id,
            latent_skill_id=latent_skill_id,
            family_meta=family_meta,
        )
        raw = await self._call_llm_async(user=user, system=system)
        # Accepted output shapes (in priority order):
        #   1. Patch schema:  {"upsert_files": {"<slug>/SKILL.md": "..."}, ...}
        #   2. Legacy:        {"skill_md": "..."}  or  {"content": "..."}
        #   3. Pure markdown (no JSON wrapper).
        # _coerce_json tolerates ```json fences and surrounding prose.
        try:
            obj = _coerce_json(raw)
        except PatchGenerationFailure:
            obj = None
        if isinstance(obj, dict):
            upserts = obj.get("upsert_files") or {}
            if isinstance(upserts, dict):
                for path, body in upserts.items():
                    if isinstance(path, str) and path.endswith("SKILL.md") and isinstance(body, str):
                        return body
            if isinstance(obj.get("skill_md"), str):
                return obj["skill_md"]
            if isinstance(obj.get("content"), str):
                return obj["content"]
        return raw

    # ------------------------------------------------------------------
    # Feedback formatting (per FeedbackLevel)
    # ------------------------------------------------------------------

    @staticmethod
    def _format_feedback(outcome: Any, level: FeedbackLevel) -> str:
        """Render a TrialOutcome into a feedback string for the LLM.

        Each level escalates the signal richness:
          - none:    empty (LLM sees no verifier signal)
          - binary:  pass/fail bit only
          - rich:    failed-tests + reward + per-group pass flags
          - process: rich + rubric dimensions + failure-pattern classification

        Both PASS and FAIL outcomes produce informative output -- needed for
        ``revision_trigger=always``, where a passed trial still triggers a
        propose() call and the LLM needs to know what worked.
        """
        if level == FeedbackLevel.NONE:
            return "(no feedback)"

        verifier_passed = getattr(outcome, "verifier_passed", None)
        if level == FeedbackLevel.BINARY:
            return f"verifier_passed: {verifier_passed}"

        # rich + process: build a structured outcome block valid for both
        # pass and fail.
        reward = getattr(outcome, "reward", 0.0)
        op = getattr(outcome, "outcome_passed", None)
        pp = getattr(outcome, "process_passed", None)
        failed = getattr(outcome, "failed_tests", []) or []

        head = (
            f"verifier_passed: {verifier_passed}\n"
            f"reward: {reward:.3f}\n"
            f"outcome_passed: {op}\n"
            f"process_passed: {pp}"
        )

        if level == FeedbackLevel.RICH:
            if verifier_passed:
                # PASS path: no failed tests by definition; surface partial
                # signal (rubric dim names if any) so the LLM has hints
                # about WHAT specifically passed.
                rubric = getattr(outcome, "rubric_dimensions", []) or []
                rubric_lines = [
                    f"  - {getattr(d, 'name', '?')}: "
                    f"{getattr(d, 'score', 0.0):.2f} / "
                    f"{getattr(d, 'weight', 0.0):.2f} weight"
                    for d in rubric
                ]
                if rubric_lines:
                    return (
                        head + "\n"
                        "## Trial passed\n"
                        "## Rubric scores (all PASS-side):\n"
                        + "\n".join(rubric_lines)
                        + "\n\n(no failed tests; this is a clean pass)"
                    )
                return head + "\n## Trial passed (no failed tests, no rubric breakdown)"
            # FAIL path: surface failure_summary if present.
            failure_summary = getattr(outcome, "failure_summary", "") or ""
            if failure_summary:
                return head + "\n## Failed tests\n" + failure_summary
            if failed:
                lines = [f"  - {t.name}: {t.message}" for t in failed]
                return head + "\n## Failed tests\n" + "\n".join(lines)
            return head + "\n## Failed (no per-test detail captured)"

        # PROCESS: rich plus group/rubric/pattern classification
        return head + "\n" + SkillAuthor._format_process_feedback(outcome)

    @staticmethod
    def _format_process_feedback(outcome: Any) -> str:
        parts: list[str] = []

        failed = getattr(outcome, "failed_tests", []) or []
        outcome_failed = [t for t in failed if getattr(t, "group", "") == "outcome"]
        process_failed = [t for t in failed if getattr(t, "group", "") == "process"]

        op = getattr(outcome, "outcome_passed", None)
        pp = getattr(outcome, "process_passed", None)

        # 1. Outcome group -- ALL failed cases
        if op is True:
            parts.append("## Outcome group: ALL PASS")
        elif op is False:
            parts.append("## Outcome group: FAILED")
            for t in outcome_failed:
                parts.append(f"  - {t.name}: {t.message}")
        else:
            parts.append("## Outcome group: (no result)")

        # 2. Process group -- ALL failed cases
        if pp is True:
            parts.append("## Process group: ALL PASS")
        elif pp is False:
            parts.append("## Process group: FAILED")
            for t in process_failed:
                parts.append(f"  - {t.name}: {t.message}")
        else:
            parts.append("## Process group: (no result)")

        # 3. Rubric dimensions -- ALL dimensions, full rationale
        rubric = getattr(outcome, "rubric_dimensions", []) or []
        if rubric:
            parts.append("## Rubric dimensions")
            for d in rubric:
                name = getattr(d, "name", "?")
                score = getattr(d, "score", 0.0)
                rationale = (getattr(d, "rationale", "") or "").strip()
                line = f"  - {name}: {score:.2f}"
                if rationale:
                    line += f"  ({rationale})"
                parts.append(line)

        # 4. Outcome pattern (covers BOTH PASS and FAIL — _classify_pattern
        # returns a "Pass (clean)" diagnostic block when op=pp=True; the
        # original label was "Failure pattern" which made the PASS case
        # read as "Failure pattern: Pass" -- contradictory and confusing).
        parts.append(f"## Outcome pattern: {SkillAuthor._classify_pattern(op, pp)}")

        return "\n".join(parts)

    @staticmethod
    def _classify_pattern(op: Any, pp: Any) -> str:
        """Map (outcome_passed, process_passed) -> a structured diagnostic block.

        Each (op, pp) combination implies a fundamentally different kind of
        skill defect, which in turn calls for a different revision strategy.
        We surface that mapping as a multi-line block with four fields the
        revision LLM can act on directly:

          - ``What this means``       what the (op, pp) combo says about the
                                      skill itself
          - ``Look in trajectory for`` the specific signals to extract from
                                      the trace
          - ``Revision direction``    concrete edit moves likely to help
          - ``Avoid``                 the most common wrong move for this
                                      class (kept inline so the LLM does not
                                      need to re-derive it)

        These are heuristics, not laws. The LLM should weigh them against
        the actual trajectory; conflicts (e.g. ``op=False, pp=True`` but the
        trajectory clearly shows a missing skill, not a wrong step) override
        the recipe.
        """
        if op is True and pp is True:
            return (
                "Pass (clean)\n"
                "  - What this means: skill is well-aligned, OR this trial\n"
                "    did not stress the skill enough to reveal weaknesses.\n"
                "  - Look in trajectory for: knowledge the agent had to\n"
                "    RE-DERIVE at runtime (paths, schema names, exact APIs,\n"
                "    conventions); non-obvious paths that worked; near-misses\n"
                "    where the agent almost picked a wrong path then\n"
                "    recovered; fragile / lucky-looking steps.\n"
                "  - Revision direction: cache the re-derived knowledge;\n"
                "    add Gotchas for near-misses; tighten fragile steps.\n"
                "    If the trajectory reveals nothing new, return the\n"
                "    existing SKILL.md verbatim (NoOp).\n"
                "  - Avoid: inflating SKILL.md with content not justified\n"
                "    by THIS trajectory; speculative adversarial gotchas\n"
                "    invented from imagination rather than evidence."
            )
        if op is True and pp is False:
            return (
                "Shortcut (op=PASS, pp=FAIL)\n"
                "  - What this means: final result is correct but the agent\n"
                "    took an improper procedural shortcut along the way --\n"
                "    a path that worked here but will not generalize / will\n"
                "    fail under variation. The skill's workflow does not\n"
                "    enforce the required procedural structure.\n"
                "  - Look in trajectory for: which prescribed step the agent\n"
                "    SKIPPED; intermediate values that were guessed or\n"
                "    pattern-matched instead of computed; signs the agent\n"
                "    pattern-matched to a hard-coded answer rather than\n"
                "    deriving it from the workflow.\n"
                "  - Revision direction: tighten the Workflow with explicit\n"
                "    procedural requirements (`MUST validate intermediate\n"
                "    output X before proceeding`); convert key steps into a\n"
                "    `- [ ]` checklist so they cannot be silently skipped;\n"
                "    consider a Tier-3 validator script that enforces the\n"
                "    procedural step.\n"
                "  - Avoid: rewriting only the description (this is a\n"
                "    workflow problem, not a retrieval problem); treating\n"
                "    this as Total Failure (the answer was right, the\n"
                "    structural support is what is missing)."
            )
        if op is False and pp is True:
            return (
                "Procedural-but-wrong (op=FAIL, pp=PASS)\n"
                "  - What this means: the agent followed the workflow\n"
                "    correctly but the workflow led to the WRONG end-state.\n"
                "    The skill is teaching a procedure that does not\n"
                "    actually solve the task class -- either the workflow\n"
                "    is missing a step, has a wrong step, terminates too\n"
                "    early, or the output format does not match what the\n"
                "    verifier expects.\n"
                "  - Look in trajectory for: the point where the agent's\n"
                "    output diverged from what the rubric expected; whether\n"
                "    the workflow's final step produces the format the\n"
                "    rubric scores; missing post-conditions (completeness,\n"
                "    format, required fields) the workflow never enforces.\n"
                "  - Revision direction: identify the wrong / missing step\n"
                "    and fix it; add an explicit POST-CONDITION check at\n"
                "    the end of the workflow (`Before claiming done, verify\n"
                "    X`); update `## Output template` if there is a format\n"
                "    mismatch; add a validation loop (do-work -> run\n"
                "    validator -> fix -> repeat).\n"
                "  - Avoid: tightening steps that already passed (pp=PASS\n"
                "    means those are fine); generic 'be careful' Gotchas --\n"
                "    name the SPECIFIC missing end-state."
            )
        if op is False and pp is False:
            return (
                "Total failure (op=FAIL, pp=FAIL)\n"
                "  - What this means: both procedure and outcome are wrong.\n"
                "    Two sub-cases, distinguishable from the trajectory:\n"
                "      (a) WRONG TOOL -- the agent abandoned the workflow\n"
                "          early and improvised, suggesting the skill\n"
                "          should not have triggered on this task at all\n"
                "          (use `operation_type=narrow`).\n"
                "      (b) WRONG WORKFLOW -- the agent followed the\n"
                "          workflow doggedly to a dead end, suggesting the\n"
                "          workflow itself is fundamentally misdirected\n"
                "          (use `operation_type=replace`, or create a NEW\n"
                "          skill in the same family per rule 5).\n"
                "  - Look in trajectory for: at what point did the agent\n"
                "    realize the skill was not helping? early abandonment\n"
                "    (case a) vs persistent doomed execution (case b)?\n"
                "    does the trajectory expose a DISTINCT capability the\n"
                "    existing skill is not the right place for?\n"
                "  - Revision direction: pick `narrow` for case (a) --\n"
                "    tighten `description` and `## When to use` to exclude\n"
                "    this context. Pick `replace` (or `create` a sibling\n"
                "    skill) for case (b) -- the workflow needs to be\n"
                "    rebuilt around the correct approach inferred from the\n"
                "    trace + plausible alternatives.\n"
                "  - Avoid: a `revise` minimal_edit (small tweaks cannot\n"
                "    fix a fundamentally misaligned skill); fragmenting\n"
                "    one skill into many tiny ones unless the trace\n"
                "    clearly shows distinct capabilities."
            )
        return (
            "Unknown (verifier produced no group results)\n"
            "  - What this means: cannot infer (op, pp) from this verifier\n"
            "    output -- treat the trajectory + reward + failure_summary\n"
            "    as the primary signal.\n"
            "  - Look in trajectory for: same signals as the other cases,\n"
            "    but rely on the raw verifier output (reward magnitude,\n"
            "    failed_tests names, exception_info) to infer where things\n"
            "    went wrong.\n"
            "  - Revision direction: use whatever signal the trajectory\n"
            "    DOES carry; if the trial is genuinely ambiguous, prefer\n"
            "    NoOp (return the existing SKILL.md verbatim) over\n"
            "    speculative edits.\n"
            "  - Avoid: speculating skill defects from a missing signal."
        )

    # ------------------------------------------------------------------
    # Prompt builders
    # ------------------------------------------------------------------

    def _render_revision_prompt(
        self,
        *,
        mode: str,
        library: Any,
        compacted: Any,
        outcome: Any,
        target_skill_ids: list[str],
        suggested_target_skill_ids: Optional[list[str]] = None,
    ) -> tuple[str, str]:
        """Build (system_prompt, user_prompt) for a revision call.

        System contains: identity + spec block + workflow rules + JSON
        contract -- all stable across calls so prompt cache hits.
        User contains: this-trial-specific data (mode, outcome with
        diagnosis_rule, cumulative trajectory, ALL family skills' SKILL.md
        content with suggested target marked, family_id).

        ``target_skill_ids`` is the FULL family-wide list of skills the
        LLM may revise (or leave unchanged). ``suggested_target_skill_ids``
        is the retriever's best guess, marked in the prompt as
        "← suggested" so the LLM has a starting point but is not
        constrained to it.
        """
        from skillevolbench.stores.library_store import skill_id_to_slug
        suggested_set: set[str] = set(suggested_target_skill_ids or target_skill_ids)
        target_blocks = []
        for sid in target_skill_ids:
            try:
                ver = library.get_skill(sid)
                content = ver.files.get("SKILL.md", "(no SKILL.md)")
            except Exception:
                content = "(skill not found)"
            slug = skill_id_to_slug(sid)
            marker = "  ← retriever suggested this as the most relevant" if sid in suggested_set else ""
            target_blocks.append(
                f"### `{slug}/SKILL.md`{marker}\n\n```\n{content}\n```"
            )

        mode_instructions = {
            "minimal_edit": "Make the smallest edit that fixes the failure. Preserve the workflow.",
            "scope_narrow": "Narrow the skill's applicability so it does not trigger on the failing context.",
            "refactor": "Refactor the skill into clearer steps; you may reorganize sections.",
            "retire_replace": "Retire the existing SKILL.md and replace it with a fresh version optimized for the failure context.",
            # No minimality bias. The spec block above already invites
            # bundled scripts/, references/, assets/ via the JSON schema --
            # this mode removes the text-only ceiling so the LLM can
            # actually use them when the failure suggests one would help.
            "free_form": (
                "Make whatever edit best closes the gap exposed by the failure. "
                "Edit SKILL.md and -- when it materially helps -- add executable "
                "`scripts/`, on-demand `references/`, or `assets/` files. "
                "Cite every Tier-3 file you add from the SKILL.md body with a "
                "clear 'when to read / run' trigger; uncited files will be rejected. "
                "Do NOT inflate the body for its own sake; size the change to the gap."
            ),
            # Hard requirement: at least one Tier-3 file MUST be present in
            # upsert_files. Used for the "is bundling Tier-3 worth it"
            # ablation -- pair with free_form (or minimal_edit) to compare.
            #
            # This text is the DELTA against system spec ?6 (which is
            # already in the system prompt and explains scripts/refs/assets
            # in full). We only repeat the MANDATE + a trial-specific
            # decision guide that maps trace patterns -> folder choice.
            # Repeating the full ?6 here would dilute the MANDATE signal
            # and waste tokens.
            "tier3_required": (
                "MANDATORY for this revision: upsert_files MUST include at "
                "least ONE new or updated file under `<slug>/scripts/`, "
                "`<slug>/references/`, or `<slug>/assets/`. A SKILL.md-only "
                "patch will be REJECTED by the parser.\n"
                "\n"
                "For folder choice + naming + hard rules, follow system "
                "spec section 6. The summary below is just a decision\n"
                "guide for picking the folder; spec 6 is the binding\n"
                "contract for HOW to write the file.\n"
                "\n"
                "DECISION GUIDE for this trial:\n"
                "  - Trace shows the agent re-deriving fragile multi-step\n"
                "    logic, OR running the same ad-hoc command repeatedly\n"
                "      -> bundle as `<slug>/scripts/<verb_object>.py`\n"
                "         and cite the exact command from SKILL.md.\n"
                "  - Trace shows the agent looking up long enum / API\n"
                "    error table / vendored doc that would bloat SKILL.md\n"
                "      -> move to `<slug>/references/<topic>.md` and cite\n"
                "         the trigger ('read this if X happens') in\n"
                "         SKILL.md.\n"
                "  - Trace shows the agent reproducing a fixed output\n"
                "    structure (template / schema / config skeleton)\n"
                "      -> bundle as `<slug>/assets/<name>.<ext>` and tell\n"
                "         SKILL.md to copy/fill.\n"
                "\n"
                "If a suitable Tier-3 file already exists in the target\n"
                "skill, UPDATE it in place -- do NOT create a near-\n"
                "duplicate.\n"
                "\n"
                "ADDITIVE BIAS still applies: cite this Tier-3 file from\n"
                "SKILL.md with a clear 'when to run / read / copy'\n"
                "trigger. Uncited files are dead weight and rejected."
            ),
            "minimal_edit_simplified": "Make a minimal edit. Output only the patched SKILL.md with one or two changed lines.",
            "minimal_edit_no_examples": "Make a minimal edit. Avoid changing or adding examples.",
        }
        mode_text = mode_instructions.get(mode, mode_instructions["minimal_edit"])

        compact_text = getattr(compacted, "text", "") or ""
        # ``slug_list`` mentions only the SUGGESTED slugs (retriever's
        # narrower pick) -- this is the "you are not constrained to..."
        # framing in the user prompt. The full ``target_skill_ids`` list
        # is shown via per-skill blocks below; LLM may revise any of them.
        slug_list = ", ".join(
            f"`{skill_id_to_slug(sid)}`" for sid in (suggested_target_skill_ids or target_skill_ids)
        )
        # ``existing_slug_list`` is the FULL set of in-family slugs --
        # surfaced inline so the user prompt can repeat the slug↔op
        # pairing constraint (system rule 5) with concrete names rather
        # than abstractly. Empty string when family has no skills yet.
        existing_slug_list = ", ".join(
            f"`{skill_id_to_slug(sid)}`" for sid in target_skill_ids
        ) or "(none)"
        n_existing = len(target_skill_ids)
        # Family for the "create new" rule -- derive from any target id
        # ("E1-LS1.x" → "E1-LS1"); rule 5 of the prompt mentions it.
        task_family_for_prompt = ""
        if target_skill_ids:
            first = target_skill_ids[0]
            if "." in first:
                task_family_for_prompt = first.split(".", 1)[0]

        # Pass-vs-fail aware framing. Both branches surface concrete data
        # via _format_feedback (now informative for both outcomes).
        # Without this branching, ``revision_trigger=always`` runs would
        # ask the LLM to "diagnose the failure" on a passed trial -- the
        # LLM would either bail or hallucinate a fix.
        verifier_passed = bool(getattr(outcome, "verifier_passed", False))
        feedback_text = self._format_feedback(outcome, self._feedback_level)
        if verifier_passed:
            outcome_section = (
                "**The trial PASSED.** Below is the verifier breakdown plus "
                "the trajectory the agent took to succeed:\n\n"
                + feedback_text
            )
            diagnosis_rule = (
                "1. **Distill the successful trajectory.** The trial passed, but the\n"
                "   trajectory often shows hidden value to encode into the skill:\n"
                "     - Knowledge the agent had to RE-DERIVE at runtime (paths, schema\n"
                "       names, exact APIs, conventions) -- cache it in SKILL.md so future\n"
                "       runs do not pay the same cost.\n"
                "     - Non-obvious paths the agent took that future runs should learn\n"
                "       (the WORKING approach, not just \"a\" working approach).\n"
                "     - Steps that worked but look FRAGILE / lucky (race-prone, version-\n"
                "       sensitive, easy to misuse) -- add a Gotcha / tighter step so the\n"
                "       skill becomes robust on next encounter.\n"
                "     - Skills the agent ALMOST MISUSED but recovered -- encode the\n"
                "       recovery as a Gotcha to prevent the near-miss next time.\n"
                "   If the trajectory shows nothing the skill can absorb (clean, generic,\n"
                "   already covered by current SKILL.md), prefer LEAVING it untouched --\n"
                "   return upsert_files containing only the existing SKILL.md text\n"
                "   verbatim (the parser will treat that as a NoOp-equivalent revise).\n"
                "   DO NOT inflate SKILL.md with content not justified by the trajectory."
            )
        else:
            outcome_section = (
                "**The trial FAILED.** Below is the verifier breakdown plus "
                "the trajectory of the failed run:\n\n"
                + feedback_text
            )
            diagnosis_rule = (
                "1. **Diagnose the trajectory.** Find the first point where the agent\n"
                "   diverged, improvised, or failed. The fix should encode THAT specific\n"
                "   missing knowledge -- typically as a new Gotcha, a tightened Workflow\n"
                "   step, a `## When to use` clarification, or a Tier-3 bundled artefact.\n"
                "   Generic prose rewrites do not help."
            )

        # Diagnosis_rule is per-outcome (PASS vs FAIL), so it lives in
        # the user message alongside outcome_section -- otherwise the
        # system prompt would have to enumerate both branches and ask
        # the LLM to pick. Cleaner to ship the right one as data.
        outcome_section = (
            outcome_section + "\n\n### Diagnosis rule for this outcome\n\n"
            + diagnosis_rule
        )
        user = _REVISE_USER_TEMPLATE.format(
            mode=mode,
            mode_instruction=mode_text,
            target_blocks="\n\n".join(target_blocks),
            slug_list=slug_list,
            existing_slug_list=existing_slug_list,
            n_existing=n_existing,
            family_id_for_this_task=task_family_for_prompt or "<unknown>",
            outcome_section=outcome_section,
            # 96K char (~24K token) cap. Sized to fit the cumulative
            # trace at T3 (3 trials * ~32K chars each, where each trial
            # now uses the bumped per-trial budget of max_total_tokens
            # = 8000 in TrajectoryCompactor). At T1/T2 most of this is
            # unused. SYSTEM (~4K tokens) is cached so the per-call
            # premium is just the user-side trace text.
            trajectory_summary=compact_text[:96000],
        )
        return _REVISE_SYSTEM, user

    def _render_induction_prompt(
        self,
        *,
        family_id: str,
        latent_skill_id: str,
        compacted: Any,
        outcome: Any,
    ) -> tuple[str, str]:
        """Build (system_prompt, user_prompt) for an induction call."""
        from skillevolbench.stores.library_store import skill_id_to_slug
        user = _INDUCE_USER_TEMPLATE.format(
            family_id=family_id,
            latent_skill_id=latent_skill_id,
            slug=skill_id_to_slug(latent_skill_id),
            verifier_passed=getattr(outcome, "verifier_passed", False),
            failure_summary=self._format_feedback(outcome, self._feedback_level),
            trajectory_summary=(getattr(compacted, "text", "") or "")[:8000],
        )
        return _INDUCE_SYSTEM, user

    @staticmethod
    def _render_zero_shot_prompt(
        *,
        family_id: str,
        latent_skill_id: str,
        family_meta: Any,
    ) -> tuple[str, str]:
        """Build (system_prompt, user_prompt) for a zero-shot draft call."""
        from skillevolbench.stores.library_store import skill_id_to_slug
        name = getattr(family_meta, "name", latent_skill_id)
        description = getattr(family_meta, "description", "")
        user = _ZERO_SHOT_USER_TEMPLATE.format(
            family_id=family_id,
            latent_skill_id=latent_skill_id,
            slug=skill_id_to_slug(latent_skill_id),
            name=name,
            description=description,
        )
        return _ZERO_SHOT_SYSTEM, user

    # ------------------------------------------------------------------
    # Parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_revision_patch(
        *,
        raw: str,
        target_skill_ids: list[str],
        triggered_by_task: str,
        failure_summary: str,
        proposing_mode: str,
        attempt_count: int,
    ) -> SkillPatch:
        from skillevolbench.stores.library_store import skill_id_to_slug

        data = _coerce_json(raw)
        op = OperationType(data.get("operation_type", "revise"))
        upserts = {str(k): str(v) for k, v in (data.get("upsert_files") or {}).items()}
        deletes = data.get("delete_paths", []) or []
        if not isinstance(deletes, list):
            raise PatchGenerationFailure("delete_paths is not a list")

        # ---- Auto-detect new skills introduced in upsert_files ----
        # Any top-level slug that has its own SKILL.md but is NOT in the
        # existing-target slug set is treated as a NEW skill creation in
        # the same family. The LLM was prompted to do this when it judges
        # the evidence as a distinct capability; the parser realises it
        # by extending target_skill_ids so LibraryStore.apply_patch builds
        # a fresh manifest entry instead of leaving an orphan file.
        existing_slug_to_sid = {
            skill_id_to_slug(sid): sid for sid in target_skill_ids
        }
        existing_slugs = set(existing_slug_to_sid)

        # Family of THIS task is derivable from any existing target
        # (target_skill_ids[0] = "<family>.<slug>") or, defensively,
        # from triggered_by_task ("E1-LS1-T2" → "E1-LS1").
        task_family = ""
        if target_skill_ids:
            first = target_skill_ids[0]
            if "." in first:
                task_family = first.split(".", 1)[0]
        if not task_family and triggered_by_task and "-T" in triggered_by_task:
            task_family = triggered_by_task.rsplit("-T", 1)[0]

        new_skill_ids: list[str] = []
        new_slugs: set[str] = set()
        for path in upserts.keys():
            top_slug = path.split("/", 1)[0]
            if top_slug in existing_slugs:
                continue   # belongs to an existing target -- normal revise
            if not path.endswith("/SKILL.md"):
                # Non-SKILL.md path under a new slug = Tier-3 file for
                # a new skill. The "create new" rule (#5 in the prompt)
                # forbids this -- new skills must be SKILL.md-only.
                raise PatchGenerationFailure(
                    f"new-skill slug {top_slug!r} bundled a non-SKILL.md "
                    f"file {path!r}; the prompt forbids Tier-3 on new "
                    "skills. Drop the file or move the new content under "
                    "an existing target slug."
                )
            new_slugs.add(top_slug)

        for slug in sorted(new_slugs):
            if not task_family:
                raise PatchGenerationFailure(
                    f"new-skill slug {slug!r} found but task family could "
                    "not be derived from target_skill_ids/triggered_by_task; "
                    "cannot validate same-family rule."
                )
            new_latent = f"{task_family}.{slug}"
            new_skill_ids.append(new_latent)

        merged_target_skill_ids = list(target_skill_ids) + new_skill_ids
        # Override op to CREATE if the patch contains any new skill --
        # apply_patch + manifest history make sense regardless, but the
        # outward operation_type makes the audit trail honest.
        if new_skill_ids:
            op = OperationType.CREATE
        elif op == OperationType.CREATE:
            # LLM claimed "create" but every upsert key is an EXISTING slug.
            # This violates the slug↔op pairing constraint in
            # _REVISE_SYSTEM rule 5. Coerce to REVISE so:
            #   (a) the audit trail honestly says "revise"
            #   (b) the LLM's tendency to wholesale-rewrite is at least
            #       LABELED correctly so downstream metrics can detect it
            # Note: this does NOT undo content damage if the LLM truly
            # rewrote the body from scratch; the additive bias in the
            # prompt is the only line of defense for that. But it stops
            # the audit trail from lying, which lets us measure the
            # damage and tighten the prompt later.
            op = OperationType.REVISE

        # ---- Tier-3 requirement check (mode-specific, EXISTING only) ----
        if proposing_mode == "tier3_required":
            tier3_on_existing = any(
                ("/scripts/" in k or "/references/" in k or "/assets/" in k)
                and (k.split("/", 1)[0] in existing_slugs)
                for k in upserts.keys()
            )
            if not tier3_on_existing:
                raise PatchGenerationFailure(
                    "tier3_required mode: upsert_files must contain at "
                    "least one Tier-3 path (scripts/ | references/ | "
                    "assets/) under an EXISTING target skill. Tier-3 "
                    "files under newly-introduced slugs are rejected by "
                    "the create-new rule, so they don't satisfy this; "
                    f"got upsert keys: {sorted(upserts.keys())}, "
                    f"existing slugs: {sorted(existing_slugs)}"
                )

        return SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=str(data.get("summary", "(no summary)"))[:200],
            upsert_files=upserts,
            delete_paths=[str(p) for p in deletes],
            target_skill_ids=merged_target_skill_ids,
            operation_type=op,
            triggered_by_task=triggered_by_task,
            triggered_by_failure_type=_classify_failure(failure_summary),
            proposing_mode=proposing_mode,
            attempt_count=attempt_count,
        )

    @staticmethod
    def _parse_create_patch(
        *,
        raw: str,
        latent_skill_id: str,
        triggered_by_task: str,
        proposing_mode: str,
    ) -> SkillPatch:
        from skillevolbench.stores.library_store import skill_id_to_slug
        slug = skill_id_to_slug(latent_skill_id)
        data = _coerce_json(raw)
        upserts = data.get("upsert_files") or {}
        if not upserts and data.get("skill_md"):
            upserts = {f"{slug}/SKILL.md": str(data["skill_md"])}
        if not upserts and data.get("content"):
            upserts = {f"{slug}/SKILL.md": str(data["content"])}
        if not upserts:
            raise PatchGenerationFailure(
                "induction LLM did not produce upsert_files / skill_md / content"
            )
        return SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=str(data.get("summary", f"Induce {latent_skill_id}"))[:200],
            upsert_files={str(k): str(v) for k, v in upserts.items()},
            delete_paths=[],
            target_skill_ids=[latent_skill_id],
            operation_type=OperationType.CREATE,
            triggered_by_task=triggered_by_task,
            proposing_mode=proposing_mode,
            attempt_count=1,
        )

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    @staticmethod
    def _fallback_chain(mode: str) -> list[str]:
        """Generate the per-failure fallback sequence."""
        primary = mode if mode in {
            "minimal_edit", "scope_narrow", "refactor", "retire_replace",
            "free_form", "tier3_required",
        } else "minimal_edit"
        seen: list[str] = []
        for m in (primary, "minimal_edit_simplified", "minimal_edit_no_examples"):
            if m not in seen:
                seen.append(m)
        return seen


# ---------------------------------------------------------------------------
# Templates (inlined; jinja2 not required)
# ---------------------------------------------------------------------------


# High-level frame given to the LLM BEFORE the detailed spec block. Answers
# three questions the LLM should keep in mind while authoring:
#   1. What is a skill (vs a task note)?
#   2. What are the three tiers (Tier 1 / Tier 2 / Tier 3)?
#   3. What mindset produces a good skill -- comprehensive, adversarial-aware,
#      written for the FUTURE agent rather than the current trace.
# Kept short on purpose; the detailed limits + best practices live in
# _SPEC_BLOCK below. Both are concatenated into every system prompt.
_SKILL_MINDSET = """\
================================================================================
WHAT A SKILL IS, AND WHAT YOU ARE BUILDING
================================================================================

A skill is a *reusable capability package* persisted on disk and loaded into
a future agent's context whenever it tackles a task in this domain. It is
NOT a one-off note about today's trial -- it must generalize to the whole
class of similar tasks, including ones the current trace did not cover.

## The three tiers (agentskills.io progressive disclosure)

  Tier 1 -- METADATA: the YAML frontmatter at the top of SKILL.md
            (`name` + `description`). ~100 tokens, ALWAYS in the agent's
            context. The description is the entire trigger surface --
            future tasks RETRIEVE this skill solely on its match against
            user prompts. Weak description = the skill never fires.

  Tier 2 -- INSTRUCTIONS: the SKILL.md body (markdown, after the
            frontmatter). Loaded ONLY when Tier 1 matches. <5000 tokens
            recommended. This is the workflow, gotchas, decision rules,
            anti-patterns, and worked examples a future agent will follow.

  Tier 3 -- RESOURCES: optional files in `<slug>/scripts/`,
            `<slug>/references/`, `<slug>/assets/`. Loaded ON DEMAND when
            SKILL.md explicitly tells the agent to run / read / copy them.
            Tier 3 holds executable validators (`scripts/`), bulky
            reference docs (`references/`), and copy-paste templates
            (`assets/`) -- material that would bloat Tier 2 if inlined.
            Uncited Tier-3 files are dead weight and rejected.

## Mindset: what makes a good skill

* **Aim for COMPREHENSIVE coverage.** The trial in front of you is one
  observation. Design the skill so it also handles the obvious harder
  variants a future task will throw -- different data shapes, missing or
  malformed fields, partial failures, cross-cutting edge cases, scaled-up
  inputs. Encode the GENERAL workflow, not just what worked today.

* **Anticipate ADVERSARIAL conditions.** Future agents will see tasks
  designed to expose weaknesses: misleading framing, edge cases that
  look like the canonical case, traps that punish "blindly follow the
  workflow" patterns, inputs crafted to make a tempting-but-wrong path
  look correct. Encode the GUARDRAILS -- validation steps, sanity
  checks, "do not rely on X when Y" anti-patterns -- that catch these
  before the agent commits to a wrong answer.

* **Write for the AGENT in the FUTURE, not for the human reading this
  trace.** The future agent will encounter cases neither you nor the
  trace has seen. Ask: what knowledge would let it succeed where it
  would otherwise fail or guess? Cache that knowledge -- runtime paths,
  schema names, exact APIs, conventions, gotchas -- so the future
  agent does not have to RE-DERIVE it.

* **Bias toward DECISION RULES** ("if X pattern appears, do Y instead
  of Z"; "before doing W, validate V"; "never call A when B is true").
  Decision rules generalize. Generic prose advice ("be careful",
  "consider edge cases") is filler.

* **Keep it CONCISE.** Comprehensive ≠ verbose. Every token in Tier 2
  is paid context for every future task. Add only what is non-obvious,
  reusable, and worth its cost. Move bulky detail to Tier 3.

* **PROCEDURAL knowledge, not EPISODIC memory.** A skill encodes
  HOW to handle a CLASS of problems. It does NOT record the specific
  answers, fixes, or trajectory steps from any single trial. WRITE:
  transferable failure patterns, reusable workflows, trigger
  conditions, validation checks, decision rules. DO NOT WRITE: the
  hard-coded fix for one task instance, a literal answer to one
  problem, the full log of a single trajectory, "in the FinGuard
  task we did X". The skill must work for tasks neither you nor the
  trace has seen.

The detailed agentskills.io spec follows; treat it as the binding
contract for shape (directory layout, frontmatter fields, Tier 3
folders, etc.).

"""


# Distilled from the agentskills.io spec, best-practices, optimizing-descriptions,
# and using-scripts pages. Embedded into every prompt so the LLM author has the
# full design contract without an external lookup.
_SPEC_BLOCK = """\
================================================================================
AGENT SKILLS -- SPEC + BEST PRACTICES (READ BEFORE WRITING)
================================================================================

## 1. Directory layout

A skill is a directory; minimum content is `SKILL.md`. Optional subdirs are
`scripts/`, `references/`, and `assets/`:

```
my-skill/
├── SKILL.md          # Required: metadata + instructions
├── scripts/          # Optional: executable code
├── references/       # Optional: documentation
├── assets/           # Optional: templates, resources
└── ...               # Any additional files or directories
```

Reference these from SKILL.md by RELATIVE path (e.g. `scripts/extract.py`,
`references/REFERENCE.md`). Keep file references one level deep.

## 2. SKILL.md format = YAML frontmatter + Markdown body

Frontmatter is the YAML between `---` markers at the very top.

| Field           | Req | Constraint                                                                           |
|-----------------|-----|--------------------------------------------------------------------------------------|
| `name`          | YES | <=64 chars; [a-z0-9-]; no leading/trailing/consecutive `-`; MUST match folder name. |
| `description`   | YES | <=1024 chars; non-empty; states WHAT the skill does AND WHEN to use it.              |
| `license`       | no  | License name or path to a bundled license file.                                      |
| `compatibility` | no  | <=500 chars; environment requirements (product, packages, network, runtime version). |
| `metadata`      | no  | Free key-value map; pick keys unlikely to collide.                                   |
| `allowed-tools` | no  | Space-separated pre-approved tools (experimental).                                   |

Minimal valid SKILL.md:

```
---
name: pdf-processing
description: Extract PDF text, fill forms, merge files. Use when handling PDFs.
---
# PDF processing
... body ...
```

The Markdown body has no enforced format. Recommended sections: step-by-step
instructions, examples, common edge cases. The full body loads into the agent
once the skill activates -- treat every token as paid context.

## 3. Progressive disclosure (THREE TIERS)

Skills load in three tiers; design for it.

  Tier 1 -- METADATA (~100 tokens, ALWAYS in context): the YAML frontmatter
            (`name` + `description`). Used by the agent's matcher to decide
            whether to load the body. A weak description = the skill never
            triggers.
  Tier 2 -- INSTRUCTIONS (<5000 tokens recommended, loaded WHEN ACTIVATED):
            the SKILL.md body. Keep it under 500 lines. Move bulky detail to
            Tier 3.
  Tier 3 -- RESOURCES (loaded ON DEMAND): files in `scripts/`, `references/`,
            `assets/`. The agent reads / runs these only when SKILL.md tells
            it to. Use this tier for big artefacts, executables, rarely
            needed detail. Cite each Tier-3 file from the body with a clear
            "when to load / run it" trigger; uncited Tier-3 files are dead
            weight.

## 4. Writing the description (Tier 1, highest leverage)

The description's CORE PURPOSE is to TRIGGER skill loading -- not to
introduce or sell the skill. The agent's matcher reads it against the
incoming user prompt; if it doesn't match, none of your Tier-2 / Tier-3
work matters because the skill never fires.

### Required ingredients (every description should contain ALL):

1. **Task object(s)** -- the concrete things the skill operates on.
   Examples: `Dockerfile`, `Express middleware`, `JSON schema`,
   `LaTeX table`, `pytest fixture`, `verifier output`, `npm package`,
   `bearer token`, `trajectory.json`. List 2-4.
2. **Action verb(s)** -- what the skill DOES with those objects.
   Examples: `inspect`, `debug`, `validate`, `summarize`, `patch`,
   `compare`, `extract`, `aggregate`, `refactor`, `migrate`. List 2-4.
3. **WHEN scenarios** -- 2-3 concrete trigger contexts in
   "Use this skill when..." form. Include INDIRECT phrasings users
   actually type ("the test is timing out", "the verifier reports
   X", "the JSON file in /tmp doesn't validate"). Synonyms count.
4. **Optional: boundary conditions** -- "Do not use this skill for
   X / Y" lines. Reduces false-positive triggers when neighbouring
   skills exist.

### Style:

- **Third-person / imperative voice**: "This skill should be used
  when..." or "Use when...". NEVER "I help with..." / "you can use
  this to...".
- **<=1024 chars hard cap.** Aim for 4-8 lines.
- **Cover INDIRECT triggers** (the user does not name the domain):
  "the failing test mentions <error>", "the spreadsheet attached",
  "the file in /tmp".

### Banned patterns (REJECTED):

- Generic catch-all words as the only signal: `debug`, `fix`,
  `code`, `bug`, `task`, `improve`, `helper`, `assist`. These match
  everything = they match nothing.
- Meta-talk about the skill itself: `"a structured workflow for..."`,
  `"this skill helps with..."`, `"records past experience"`,
  `"saves the agent from..."`. Dilutes keyword signal.
- Self-referential phrasing: `"This skill records what we learned
  in trial X"`. Skills describe TASK DISTRIBUTIONS and TRANSFERABLE
  OPERATIONS, not their own provenance.
- Walking the body: don't put the workflow steps in the description.
  Description = WHEN to fire; body = WHAT to do.

### Concrete examples:

  GOOD (auth-bypass family in Express/Node):
    "Diagnose and fix bearer-token / JWT authentication-bypass bugs
    in Node.js / Express middleware where invalid or malformed
    tokens leak protected user data. Use when an auth middleware
    (`tokenValidator`, `roleChecker`, `tokenPolicy`) defers errors
    instead of returning 401, when `/api/users`-style routes return
    user records under bad tokens, when soft-fail / monitor-only
    auth modes mask 401-worthy failures, or when the verifier
    reports user-data fields (`email`, `phone`, `ssn_last4`)
    leaking through 200 responses. Do not use this skill for plain
    role/RBAC bugs where authentication itself is correct."

  POOR (does NOT trigger reliably):
    "Use when debugging a software bug. Provides a structured,
    step-by-step workflow for identifying the root cause."
    -- generic; no task object, no domain keyword; matches every
    coding task = matches none in practice.

## 5. Body best practices

The body is what the agent reads AFTER the description triggers. Its
job is PROCEDURAL: tell the agent what to do, in order, with
explicit branches. It is NOT a paper, a textbook chapter, or a
narrative summary.

### What the body MUST cover (when applicable):

- **Goal statement** -- one sentence: what does success look like.
- **When to use** -- echo the description's WHEN scenarios, more
  concretely. May include "do not use when..." boundaries.
- **Workflow** -- numbered or `- [ ]`-checklist of action steps in
  order. Each step starts with an action verb ("First inspect...",
  "Then verify...", "If X, do Y; else do Z."). NOT prose paragraphs.
- **Gotchas** -- concrete near-miss / failure patterns the agent
  will hit otherwise (soft-deletes, ID renames, health checks that
  lie, off-by-one timezone drift). Decision-rule form.
- **Resource map** -- a short table or list mapping triggers to
  Tier-3 files: "Run `scripts/X.py` when ...", "Read
  `references/Y.md` if ...", "Use `assets/Z.tmpl` to format ...".
  REQUIRED whenever the skill has Tier-3 files.
- **Output format / completion criteria** -- when the task expects
  a specific output shape, embed a literal template (agents
  pattern-match against concrete structures better than prose).
- **Uncertainty handling** -- "if information X is missing, do Y
  before proceeding" / "if validator output is ambiguous, default
  to the SAFER branch". Tells the agent how to act under partial
  information rather than guessing.

### Style requirements:

- **Action-oriented language.** Every step starts with a verb in
  imperative or "First / Then / If / Avoid" form. NO sentences like
  "It is important to note that...".
- **Decision rules over advice.** "If <pattern>, do <action>" beats
  "consider edge cases" / "be careful".
- **Defaults over menus.** Pick ONE recommended path; relegate
  alternatives to a brief "Alternatives" line. Forcing the agent to
  re-decide every call wastes tokens.
- **Match specificity to fragility.** PRESCRIPTIVE on fragile /
  destructive / order-sensitive steps; PERMISSIVE on creative
  steps. Mixing both within one SKILL.md is fine.
- **One worked example** beats exhaustive documentation. Trust the
  agent's general competence on syntax / language basics.
- **Validation loop.** When the workflow is iterative: do-work,
  run-validator (a `scripts/` file or shell command), fix, repeat.
  State the validator command explicitly.
- **Plan-validate-execute** for batch / destructive ops: agent
  produces a structured plan, validates against a source of truth,
  THEN executes.

### What the body MUST NOT contain:

- Background essays / theory dumps that the agent already knows
  (basic Python syntax, "what is JWT", "what is Docker").
- A literal log of any single trial's trajectory.
- Hard-coded answers / fixes for one task instance ("change line
  43 of tokenValidator.js to..." for a specific repo). Encode the
  PATTERN ("when soft-fail logic defers auth errors, remove the
  defer branch and return 401 + log") instead.
- Long enumerations (full enum tables, exhaustive API listings) --
  move those to `references/<topic>.md`.
- Resources without a citation. If you bundle `scripts/foo.py` you
  MUST tell the agent in the body: WHEN to run it, exact command,
  expected output, how to interpret failure.

### The body must be READABLE COLD by a future agent.

Assume the agent has zero memory of any past trial. Don't write
"as before" / "as in the previous task" / "the same fix as last
time". Every reference must be self-contained.

## 6. Tier-3 directories

The agent's mental model: it RUNS files in `scripts/`, READS files in
`references/`, COPIES files in `assets/`. Place each file by its
intended interaction.

Every Tier-3 file MUST be cited from SKILL.md with a clear
"when to run / read / copy" trigger. Uncited Tier-3 files are dead
weight and rejected.

Naming (all three dirs):
  - Specific verb_object pattern preferred:
    `validate_skill_frontmatter.py`, `extract_failure_modes.py`,
    `compare_skill_versions.py`, `failure_patterns.md`,
    `result_schema.json`, `report_template.md`.
  - REJECTED: vague names like `helper.py`, `notes.md`, `more.md`,
    `stuff.txt`, `template2.md`, `old.json`, `doc1.md`.

---

`scripts/` -- EXECUTABLE CODE the agent RUNS.

What goes here: deterministic, repeatable operations. Examples for
benchmarking-style domains: `parse_trajectory.py`,
`extract_failure_modes.py`, `validate_skill_frontmatter.py`,
`check_skill_patch.py`, `summarize_verifier_logs.py`,
`aggregate_results.py`, `compare_quotes.py`.

When to bundle one: trace shows the agent RE-DERIVING the same
logic, OR the step is fragile and a tested script beats freeform
generation.

Hard rules (REJECTED otherwise):
  - **CLI**: clear arg interface; `--help` with brief description +
    flags + examples.
  - **Output**: structured (JSON / CSV / TSV) on stdout;
    diagnostics on stderr; deterministic given same inputs.
  - **Errors**: explain WHAT went wrong, WHAT was expected, WHAT to
    try. NOT bare tracebacks.
  - **Exception handling** for common failure modes: missing file,
    malformed JSON / YAML, schema invalid, missing required field.
  - **Idempotent** (agents retry).
  - **Closed-set / enum** params for ambiguous choices.
  - **`--dry-run`** for destructive ops; non-default for any
    deletion / overwrite. NEVER default to deleting files,
    overwriting results, or clearing dirs.
  - **No interactive prompts**; agents run non-interactive shells.
  - **No silent network installs**; declare deps inline (PEP 723
    `# /// script` for Python; `npm:` for Deno; etc.) or in
    SKILL.md `compatibility` field.
  - **Meaningful exit codes**, documented in `--help`.
  - **Predictable output size**; support `--output FILE` for large.

SKILL.md must specify, per script: WHEN to run, exact command,
expected output shape, how to interpret failure.

---

`references/` -- ON-DEMAND DOCUMENTATION the agent READS.

What goes here: long-form material that would bloat SKILL.md if
inlined. Each file serves ONE clear topic. Examples for a
benchmarking / self-evolving domain:
  - `failure_patterns.md` -- catalogue of TRANSFERABLE failure modes
    (NOT single-trial details).
  - `update_policy.md` -- when a skill update is allowed vs.
    rejected.
  - `procedural_skill_rubric.md` -- what makes a skill "good".
  - `benchmark_task_schema.md` -- task spec / verifier interface.
  - `trajectory_analysis_protocol.md` -- step-by-step trace review.
  - `skill_patch_rubric.md` -- patch acceptance criteria.

Conventions:
  - One topic per file. Filename describes the topic in 2-4 words.
  - Long files (>200 lines): start with a TOC.
  - SKILL.md links each reference DIRECTLY: "Read
    `references/failure_patterns.md` if the verifier reports
    pattern Y". NO daisy-chained jumps (ref → ref → ref).
  - NO `references/all.md` dumping ground.
  - NO obviously expired or task-instance-specific content unless
    explicitly marked.

---

`assets/` -- STATIC RESOURCES the agent COPIES / FILLS / EMBEDS
verbatim (never executed, rarely "read for understanding").

What goes here: document templates, config skeletons, prompt
scaffolds, lookup tables, JSON / YAML schemas, LaTeX templates,
sample input/output pairs. Examples:
  - `skill_template.md`
  - `skill_patch_template.md`
  - `result_schema.json`
  - `evaluation_table_template.tex`
  - `report_template.md`

Conventions:
  - Files are STRUCTURED, REUSABLE, READY to drop in with minimal
    edits.
  - SKILL.md tells the agent WHEN to use each: "Use
    `assets/report_template.md` as the output structure; replace
    `{{placeholders}}`".
  - REJECTED here: long manuals (those go to `references/`),
    backup / dead files, random notes, unused data.

## 7. One-off commands (no `scripts/` needed)

If an existing tool already does the job, reference it directly with a
pinned version: `uvx ruff@0.8.0 check .`, `npx eslint@9 --fix .`, etc.
State runtime prerequisites in SKILL.md or in the `compatibility`
frontmatter field.

## 8. Self-evolving skill discipline (HARD)

You are part of an evolving library: skills get revised after each
trial. That makes the line between "transferable knowledge" and
"trial-specific noise" critical. Discipline:

### What a skill MUST be:

- A description of a TASK DISTRIBUTION + the TRANSFERABLE OPERATIONS
  that solve it.
- A workflow that works on tasks the current trace did NOT cover.
- A library of failure patterns + decision rules that generalize.

### What a skill MUST NOT be:

- A log of any single trajectory.
- A specific answer to one task instance ("the fix is to delete
  line 43 of `tokenValidator.js`").
- A scrapbook of "what we learned in trial X".

### Update policy (applies to every revise / propose call):

- **Update when** the trace shows a failure pattern that is likely
  REPEATABLE across the family, AND the fix can be encoded as a
  decision rule / workflow step / Tier-3 artefact that future agents
  can apply WITHOUT having seen this trial.
- **Do NOT update** for a one-off quirk that only this task instance
  exhibits. Silently accept the existing skill (NoOp-equivalent
  revise: return SKILL.md verbatim).
- **Do NOT inflate** the body just to "have something to say".
  If the trace teaches nothing new, NoOp.
- **NEVER write task-specific answers** into SKILL.md / references/
  / assets/. That pollutes the library and biases future tasks.

### Patch self-review checklist (run mentally before emitting JSON):

- [ ] Is every change driven by a pattern that will recur, not by
      this trial's specific symptoms?
- [ ] Could a future agent, given only the new SKILL.md (no trace),
      apply the workflow to a DIFFERENT task in this family?
- [ ] Is the description still a strong trigger (≥5 domain
      keywords; concrete WHEN scenarios)?
- [ ] Does every Tier-3 file have a clear "when to run / read /
      copy" trigger in SKILL.md?
- [ ] Did I avoid copy-pasting trajectory text or task-instance
      identifiers (file paths specific to this repo, exact line
      numbers, the literal failing input)?

If any answer is "no", revise the patch before submitting.
================================================================================
"""


_REVISE_SYSTEM = """\
You are a skill-evolution assistant maintaining a shared library of
procedural skills used by an LLM agent. Your role on this call is to
REVISE existing SKILL.md content (and optionally bundled Tier-3 files)
based on a recent task trial. Output STRICT JSON.

""" + _SKILL_MINDSET + _SPEC_BLOCK + """

================================================================================
HOW TO PROCESS A REVISION REQUEST
================================================================================

The user message provides, in order:
  ## Revision mode + mode-specific instruction
  ## Trial outcome (PASS or FAIL banner + verifier breakdown + diagnosis_rule)
  ## Compacted trajectory (the agent's recent run)
  ## Target skills (slug list + task family + current SKILL.md content)

Apply these workflow rules (in addition to the spec block above):

1. **Apply the diagnosis_rule** provided in the trial-outcome section.
   The PASS branch and the FAIL branch ask for different things; do NOT
   substitute one for the other. If passed and the trajectory shows
   nothing the skill can absorb, return upsert_files containing only the
   existing SKILL.md text verbatim -- the parser treats that as NoOp.

2. **Respect the layering** (see Progressive Disclosure in the spec):
   - Don't bloat SKILL.md with material that belongs in `references/`
     (long enums, edge-case catalogues, vendored API docs).
   - Don't shrink the `description` for token savings -- discoverability
     beats a few chars.
   - Don't change `name` unless operation_type=replace; renaming breaks
     the folder-slug match.
   - **`description` quality is the trigger surface** (Tier-1, always
     in future agents' context). When you revise, AUDIT the existing
     `description`. If it is generic ("Use when debugging a software
     bug.") or lacks domain keywords, REWRITE it to satisfy ALL of:
       a. <=1024 chars, imperative voice.
       b. AT LEAST 5 concrete keywords from the trajectory's domain
          (file types, tool names, error symptoms, library names,
          API verbs, domain terms). Generic words ("debug", "fix",
          "code", "bug", "task") DO NOT count.
       c. WHAT + WHEN: 2-3 concrete trigger contexts including
          INDIRECT ones (where the user does NOT name the skill
          domain).
       d. No meta-talk ("a structured workflow for...", "this skill
          helps with..."). It dilutes keyword signal.
     A weak description = the skill never fires on future tasks =
     all your other revisions are wasted.

3. **operation_type semantics**:
   - `revise`  -- normal edit; same name, same intent.
   - `narrow`  -- tighten `description` / `## When to use` so the skill no
                  longer triggers on the failing context.
   - `replace` -- full rewrite; only when minor edits cannot fix the
                  pattern.
   - `create`  -- introduces a new skill (see rule 5; must be in the
                  same family as the current task).

4. **Tier-3 files** (scripts/, references/, assets/) on EXISTING skills
   MUST be cited from SKILL.md with a clear "when to read / run / copy"
   trigger. Uncited Tier-3 files are dead weight -- the parser rejects
   them.

5. **Update existing vs create new (SAME FAMILY ONLY).**

   When the family already has skills (shown in the "Skills in family"
   block of the user message), your DEFAULT action is to SELECT ONE OR
   MORE of them and REFINE them in place. Creating a brand-new sibling
   is the exception, not the default.

   ADDITIVE BIAS for revisions:
   - PRESERVE the existing SKILL.md structure, naming, and intent
     unless the trajectory shows specific content is wrong, misleading,
     or unsafe.
   - PREFER ADDING over REPLACING: a new Gotcha, a tightened Workflow
     step, a refined `## When to use` clarifier, an extra cited Tier-3
     file, a sharper one-line summary in the frontmatter.
   - You MAY rewrite a section ONLY if the trajectory shows that
     section was wrong; cite the failing step in `summary`.
   - DO NOT shrink, gut, or wholesale-rewrite an existing SKILL.md
     "for clarity" / token savings -- accumulated knowledge IS the
     point of the library.
   - If the SKILL.md is fundamentally misaligned with the trajectory
     (rare), use operation_type=`replace` -- NEVER `create` with the
     same slug (see slug↔op pairing below).

   SLUG ↔ operation_type pairing (HARD CONSTRAINT):
   - Reusing a slug already shown in "Skills in family" → op MUST be
     `revise` / `narrow` / `replace`. NEVER `create`.
   - `create` → MUST use a brand-new slug not visible in that block.
   - Violations are REJECTED by the parser.

   You MAY create a new skill IFF the trajectory exposes a genuinely
   DISTINCT capability the existing skill is not the right place for
   (different workflow / problem space / prerequisites).

   To create a new skill in the task's family:
   a. Pick a NEW slug. Naming rules (mandatory):
      - Lowercase ASCII letters, digits, and `-` only (kebab-case)
      - Describes the capability concisely (3-6 hyphen-separated words)
      - Globally unique across ALL families. Check the existing slug
        list in the user message and avoid any visible name.
      - Do NOT include the family_id in the slug; the parser composes
        the formal id as `<task_family_id>.<your_slug>`.
   b. Add EXACTLY ONE entry to upsert_files:
        "<your_slug>/SKILL.md": "<full SKILL.md content>"
      The folder name and SKILL.md frontmatter `name` MUST match.
   c. NO Tier-3 files for new skills. The parser REJECTS Tier-3 paths
      under a new slug. Tier-3 is reserved for revisions to existing
      skills (rule 4).
   d. The new skill is recorded as `<task_family_id>.<your_slug>` --
      you cannot create a skill in another family from this task.
   e. In `summary`, state you are creating a new skill and briefly
      justify why no existing skill could absorb the evidence.

   Updating an existing skill AND creating a new skill in the same patch
   is allowed -- list both under upsert_files. Set operation_type to
   "create" if any new slug is involved, otherwise "revise" / "narrow"
   / "replace" per rule 3.

## Required JSON output

Return EXACTLY one JSON object with these keys:

```
{
  "summary": "<one short sentence describing the change>",
  "operation_type": "revise" | "narrow" | "replace" | "create",
  "upsert_files": {
    "<slug>/SKILL.md": "<full new SKILL.md content>",
    "<slug>/scripts/<file>": "<optional, only if SKILL.md cites it>",
    "<slug>/references/<file>": "<optional, only if SKILL.md cites it>",
    "<slug>/assets/<file>": "<optional, only if SKILL.md cites it>"
  },
  "delete_paths": []
}
```

Always include FULL file content -- never diffs. Include only files you
actually edited or created. No commentary outside the JSON.
"""


_REVISE_USER_TEMPLATE = """\
## Revision mode: {mode}

{mode_instruction}

## Trial outcome

{outcome_section}

## Cumulative trajectory across this family's learning trials

The trace below concatenates ALL prior learning-block trials in this
family (T1, T2, ...) plus the trial that just finished. Each chunk is
delimited by a `## Past trial:` or `## Current trial:` header. Reflect
across the full episodic history -- patterns that appear repeatedly are
stronger evidence than single-trial signals.

```
{trajectory_summary}
```

## Skills in family `{family_id_for_this_task}`

This family has {n_existing} active skill(s): {existing_slug_list}.

**Default action when skills exist: SELECT ONE OR MORE of them and
REFINE in place.** Apply the additive bias from system rule 5 --
preserve existing structure and content; ADD what the trajectory
teaches (gotchas, tightened steps, refined frontmatter summary, cited
Tier-3 files). Do NOT rewrite or shrink existing SKILL.md content
unless the trajectory proves a specific section is wrong.

The retriever suggested {slug_list} as the most relevant edit point
("← retriever suggested" marker), but you are NOT constrained to it
-- you may:

  - revise the suggested skill (additive refinement; default),
  - revise multiple skills in this family in one patch,
  - revise a DIFFERENT skill in this family that the trajectory shows
    is actually wrong / incomplete,
  - leave one skill untouched and edit another,
  - create a NEW sibling skill ONLY if the trajectory exposes a
    genuinely distinct capability the existing skills cannot absorb
    (see system prompt rule 5),
  - return all current SKILL.md content verbatim if the trajectory
    adds nothing new (NoOp-equivalent).

**REMINDER (system rule 5 hard constraint):** the slugs listed above
({existing_slug_list}) MUST NOT be reused under operation_type=`create`.
For those slugs use `revise` / `narrow` / `replace`. `create` is only
valid with a brand-new slug.

{target_blocks}
"""


_INDUCE_SYSTEM = """\
You are a skill-evolution assistant maintaining a shared library of
procedural skills used by an LLM agent. Your role on this call is to
INDUCE a NEW skill from an LLM agent's recent task experience -- this
is the FIRST version of this skill in the library. Output STRICT JSON.

""" + _SKILL_MINDSET + _SPEC_BLOCK + """

================================================================================
HOW TO PROCESS AN INDUCTION REQUEST
================================================================================

The user message provides:
  ## Family id, latent skill id, slug
  ## Last task verdict (verifier_passed + failure_summary)
  ## Compacted trajectory (your only ground-truth evidence)

Apply these induction rules (in addition to the spec block above):

1. **The trajectory is your evidence.** Treat it like a debrief:
   - Where did the agent stumble, improvise, retry, or miss the obvious?
     Those moments become Gotchas, Workflow steps, or bundled scripts.
   - What context (file paths, schema names, exact APIs, conventions)
     did the agent have to discover at runtime? Encode it directly so
     future runs do not.
   - Skip what the agent already knows (language syntax, file formats,
     standard libraries). Only project- and domain-specific knowledge
     that the agent had to RE-DERIVE.

2. **Frontmatter** -- `name` and `description` (HARD constraints):

   `name` MUST equal the slug given in the user message.

   `description` is the entire trigger surface (Tier-1, always in
   future agents' context). A weak description = the skill never
   fires. REQUIREMENTS:

   a. <=1024 chars, imperative voice ("Use this skill when...").
   b. **Keyword density**: list AT LEAST 5 concrete keywords
      extracted from the trajectory's task domain -- file types,
      tool names, error symptoms, library/framework names, API
      verbs, domain terms. Generic words ("debug", "fix", "code",
      "bug", "task") DO NOT count as keywords.
   c. **State WHAT (capability) AND WHEN (trigger contexts)**, not
      just one. The "when" should list 2-3 concrete trigger contexts
      -- including INDIRECT ones where the user does NOT name the
      skill domain ("the spreadsheet attached", "the file in /tmp",
      "the failing test mentions <error>"). Synonyms count.
   d. NO meta-talk about the skill itself ("a structured workflow
      for...", "this skill helps with...") -- agents skim
      descriptions and meta-talk dilutes keyword signal.

   GOOD example (for a hypothetical auth-bypass family):
     "Diagnose and fix bearer-token / JWT authentication bypass
     bugs in Node.js / Express middleware where invalid tokens leak
     protected user data. Use when an Express auth middleware
     (tokenValidator, roleChecker, tokenPolicy) defers errors,
     when /api/users-style routes return user records under bad
     tokens, when soft-fail / monitor-only auth modes mask
     401-worthy failures, or when the verifier reports user-data
     fields (email, phone, ssn_last4) leaking through 200
     responses."

   POOR example (does NOT trigger reliably):
     "Use when debugging a software bug. Provides a structured,
     step-by-step workflow for identifying the root cause."
     -- no domain keywords; "debug a software bug" matches
     everything = matches nothing.

3. **Recommended body sections** (omit ones you don't need):
   `# <title>` -> `## When to use` -> `## Workflow` -> `## Examples`
   -> `## Gotchas` -> `## Output template`.
   Gotchas is usually the single highest-value section -- write it
   when the trajectory shows any near-miss or recovery.

4. **Pick ONE default path** in the workflow; relegate alternatives to
   a brief "Alternatives" line.

5. **Tier-3 files** are optional. Add a `<slug>/scripts/<file>` only
   when the trajectory shows the agent re-deriving the same logic or
   the step is fragile enough that a tested script beats freeform
   generation. Use `<slug>/references/<file>` for long material loaded
   on demand. Use `<slug>/assets/<file>` for verbatim templates. Every
   Tier-3 file MUST be cited from SKILL.md body with a clear trigger;
   uncited Tier-3 files are dead weight.

## Required JSON output

```
{
  "summary": "<one short sentence>",
  "operation_type": "create",
  "upsert_files": {
    "<slug>/SKILL.md": "<full SKILL.md, YAML frontmatter first>",
    "<slug>/scripts/<file>": "<optional, only if SKILL.md cites it>",
    "<slug>/references/<file>": "<optional, only if SKILL.md cites it>",
    "<slug>/assets/<file>": "<optional, only if SKILL.md cites it>"
  }
}
```

Minimal acceptable output is just the `<slug>/SKILL.md` entry.
"""


_INDUCE_USER_TEMPLATE = """\
## Family id

{family_id}

## Latent skill id (formal, internal handle)

{latent_skill_id}

## Slug (folder name AND frontmatter `name` -- MUST be identical)

{slug}

## Last task verdict

verifier_passed: {verifier_passed}
failure_summary: {failure_summary}

## Compacted trajectory (your only ground-truth evidence)

```
{trajectory_summary}
```
"""


_ZERO_SHOT_SYSTEM = """\
You are a skill-evolution assistant maintaining a shared library of
procedural skills used by an LLM agent. Your role on this call is to
DRAFT a procedural skill BEFORE the agent has executed any task in
this family -- you only have the family label and a brief description,
NO execution trace yet. Output STRICT JSON.

(Mindset note for ZERO-SHOT: cast a WIDE net on triggers and workflow
shape, but do NOT invent project-specific gotchas / examples / numbers
-- you have no evidence yet. T1's induction will fill those in once a
real trace exists. The "comprehensive + adversarial" mindset below
applies to the GENERAL category, not to invented specifics.)

""" + _SKILL_MINDSET + _SPEC_BLOCK + """

================================================================================
HOW TO PROCESS A ZERO-SHOT DRAFT REQUEST
================================================================================

The user message provides:
  ## Family id, latent skill id, slug
  ## Family name + description (your only inputs -- no trace, no outcome)

Apply these zero-shot rules (in addition to the spec block above):

You are writing Tier 1 + Tier 2 ONLY. Tier 3 (`scripts/`, `references/`,
`assets/`) MUST NOT be created yet -- wait until T1's real execution
reveals what's worth caching.

1. **No invented gotchas, no invented examples.** You have no execution
   evidence. Inventing project quirks would mislead the agent. Leave
   `## Gotchas` and `## Examples` for T1 induction to fill in from the
   real trace.

2. **Frontmatter** -- `name` and `description` (HARD constraints):

   `name` MUST equal the slug given in the user message.

   `description` is the entire trigger surface (Tier-1, always in
   future agents' context). REQUIREMENTS:

   a. <=1024 chars, imperative voice ("Use this skill when...").
   b. **Keyword density**: extract AT LEAST 5 concrete keywords
      from the FAMILY description / family name provided in the
      user message -- domain terms, tool names, error patterns,
      file types, library names. Generic words ("debug", "fix",
      "code", "bug") DO NOT count.
   c. **State WHAT (capability) AND WHEN (trigger contexts)**.
      Cast WIDE here (T1 induction will narrow once a real trace
      exists). List 3-5 trigger contexts including INDIRECT ones
      where the user does NOT name the skill domain.
   d. NO meta-talk about the skill itself ("a structured workflow
      for...", "this skill helps with...") -- dilutes signal.

   POOR example (does NOT trigger reliably):
     "Use when debugging a software bug. Provides a structured,
     step-by-step workflow for identifying the root cause."
     -- generic, no domain keywords; matches everything = matches
     nothing.

3. **Body** (only the sections you can honestly write without a trace):
   - `# <title>` -- one line.
   - `## When to use` -- bullet list of trigger conditions (cast wider
     than the description).
   - `## Workflow` -- best-guess numbered procedure based on the family
     description. Prescriptive on obviously fragile / order-sensitive
     steps; permissive on creative ones.
   - `## Output template` -- only if the family description implies a
     fixed output shape; otherwise omit.

4. **One default path, no menus.** If multiple approaches are plausible,
   pick the most common one and move on.

5. **Keep the body under ~200 lines.** Post-T1 revision will refine it;
   over-investing now will mostly be rewritten.

## Required JSON output

```
{
  "summary": "<one short sentence>",
  "operation_type": "create",
  "upsert_files": {
    "<slug>/SKILL.md": "<full SKILL.md content, YAML frontmatter first>"
  }
}
```

Legacy single-key form is also accepted for backward compatibility:
`{"summary": "...", "skill_md": "<SKILL.md content>"}`.
"""


_ZERO_SHOT_USER_TEMPLATE = """\
## Family id

{family_id}

## Latent skill id (formal, internal handle)

{latent_skill_id}

## Slug (folder name AND frontmatter `name` -- MUST be identical)

{slug}

## Family name

{name}

## Family description

{description}

## Output format

Return your response as a single JSON object exactly per the schema in the system prompt.
"""


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


def _coerce_json(raw: str) -> dict[str, Any]:
    """Parse LLM output as JSON, tolerating prefix/suffix prose."""
    raw = (raw or "").strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass
    m = _JSON_OBJECT_RE.search(raw)
    if not m:
        raise PatchGenerationFailure("LLM output did not contain a JSON object")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as exc:
        raise PatchGenerationFailure(f"could not parse JSON: {exc}") from exc


def _classify_failure(summary: str) -> Optional[str]:
    if not summary:
        return None
    lowered = summary.lower()
    if "import" in lowered or "modulenotfound" in lowered:
        return "import_error"
    if "type" in lowered:
        return "type_error"
    if "key" in lowered:
        return "key_error"
    if "timeout" in lowered:
        return "timeout"
    if "process" in lowered or "shortcut" in lowered:
        return "process_failure"
    return "outcome_failure"


def _no_sync(_prompt: str) -> str:
    raise NotImplementedError(
        "SkillAuthor was constructed without an LLM client. Inject a "
        "sync_call / async_call or rely on the LiteLLMClient default."
    )


def _wrap_sync_as_async(fn: SyncCall) -> AsyncCall:
    async def _wrapper(prompt: str) -> str:
        return fn(prompt)
    return _wrapper


__all__ = [
    "SkillAuthor",
    "PatchGenerationFailure",
    "LiteLLMClient",
    "SyncCall",
    "AsyncCall",
]
