"""Cost metrics (Part 10 §12.8).

Two layers of cost tracking:

* **Agent side** (per trial) -- token counts + USD pulled from
  ``trial_result.context`` which Harbor populates from the agent CLI's
  ATIF ``trajectory.json:final_metrics``. Stored on each ReplayRecord.

* **Host side** (per run) -- token counts + USD accumulated by the
  ``LiteLLMClient`` instances that drive ``SkillAuthor.propose`` /
  ``induce_skill`` / ``zero_shot_create`` and ``LLMSelfRetriever``.

Both feed into :class:`CostReport` -- the report exposes ``agent_cost_usd``,
``host_cost_usd``, and ``total_cost_usd`` plus per-side token breakdowns.

Pricing convention follows SkillFlow's table: input / output / cache
rates per million tokens. ``cache`` rate covers the heavy discount that
Bedrock / Anthropic / OpenAI give for cache-read tokens (10x cheaper).
``compute_cost_usd`` falls back to ``None`` when the model isn't priced.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional


# ---------------------------------------------------------------------------
# Pricing table (USD per million tokens)
# ---------------------------------------------------------------------------
# Rates are best-effort current-as-of-writing; update from provider docs
# before billing-sensitive estimates. Imported model identifiers go through
# ``canonicalize_model_name`` so prefixes like ``bedrock/us.anthropic.``
# and ``openai/`` are stripped before lookup.
# Verified 2026-05-03 against vendor pricing pages. Only the models we
# actually run are listed (configs/models/*.yaml). When a model isn't
# here, ``compute_cost_usd`` returns ``None`` and ``cost_source`` becomes
# ``"unknown"`` -- we never silently fall back to $0.
#
# Notes for tiered models:
#   * gemini-2.5-pro / gemini-3.1-pro both have a >200k-token tier where
#     the rate roughly doubles. Our experiment prompts stay well under
#     200k, so we use the <=200k tier; revisit if you start running long-
#     context evaluations.
#   * claude-opus-4.x supports a 1.1x premium for US-only data residency
#     (inference_geo). We use the global rate.
MODEL_PRICING_USD_PER_MILLION: dict[str, dict[str, float]] = {
    # Anthropic Claude (Bedrock pricing matches Anthropic 1P API; global)
    "claude-opus-4.5":              {"input": 5.0,    "output": 25.0,   "cache": 0.5},
    "claude-opus-4.6":              {"input": 5.0,    "output": 25.0,   "cache": 0.5},
    "claude-sonnet-4.5":            {"input": 3.0,    "output": 15.0,   "cache": 0.3},
    "claude-sonnet-4.6":            {"input": 3.0,    "output": 15.0,   "cache": 0.3},
    # Moonshot Kimi (platform.moonshot.ai official 2026-05; was 0.60 input,
    # 3.00 output, 0.10 cache -- prior table understated by ~2x).
    "kimi-k2.5":                    {"input": 0.60,   "output": 3.00,   "cache": 0.10},
    # OpenAI GPT-5 (developers.openai.com/api/docs/pricing)
    # NOTE: 5.2-codex and 5.3-codex share the same Codex-line rate.
    "gpt-5.4":                      {"input": 2.5,    "output": 15.0,   "cache": 0.25},
    "gpt-5.3-codex":                {"input": 1.75,   "output": 14.0,   "cache": 0.175},
    "gpt-5.2-codex":                {"input": 1.75,   "output": 14.0,   "cache": 0.175},
    # Google Gemini (ai.google.dev/gemini-api/docs/pricing) -- <=200k tier.
    # gemini-3-flash is what we actually run (canonicalized from
    # ``gemini-3-flash-preview``); no plain ``gemini-3.1-flash`` exists yet.
    "gemini-3.1-pro":               {"input": 2.0,    "output": 12.0,   "cache": 0.20},
    "gemini-3-flash":               {"input": 0.50,   "output": 3.00,   "cache": 0.05},
    "gemini-2.5-pro":               {"input": 1.25,   "output": 10.0,   "cache": 0.125},
}

# Aliases that don't fit the simple-strip rule.
MODEL_NAME_ALIASES: dict[str, str] = {
    "moonshotai.kimi-k2.5":          "kimi-k2.5",
    "moonshotai/moonshotai.kimi-k2.5": "kimi-k2.5",
}


def canonicalize_model_name(model_name: Optional[str]) -> Optional[str]:
    """Map a litellm-style model id to a row in MODEL_PRICING_USD_PER_MILLION.

    Examples:
      ``bedrock/us.anthropic.claude-opus-4-5-20251101-v1:0`` -> ``claude-opus-4.5``
      ``openai/gpt-5.4``                                     -> ``gpt-5.4``
      ``gemini/gemini-3.1-pro-preview``                      -> ``gemini-3.1-pro``
      ``gemini/gemini-3-flash-preview``                      -> ``gemini-3-flash``
      ``openai/moonshotai.kimi-k2.5``                        -> ``kimi-k2.5``

    Returns ``None`` for models we don't have pricing for (e.g.
    ``kimi-k2-thinking``); callers report this as ``cost_source="unknown"``.
    """
    if not model_name:
        return None

    normalized = model_name.strip().lower()
    # Strip vendor prefix.
    for prefix in ("openai/", "moonshot/", "moonshotai/", "google/",
                   "anthropic/", "gemini/", "bedrock/"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # Strip cross-region inference profile prefixes.
    for prefix in ("us.", "eu.", "apac.", "aws.", "vertex."):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix):]
            break

    # Anthropic Bedrock-style ids: anthropic.claude-opus-4-5-20251101-v1:0
    # → reduce to claude-opus-4.5 (handle the dash-vs-dot version).
    if normalized.startswith("anthropic."):
        normalized = normalized[len("anthropic."):]
    if "-" in normalized and normalized.startswith("claude-"):
        # Map "claude-opus-4-5-..." to "claude-opus-4.5"
        parts = normalized.split("-")
        if len(parts) >= 4 and parts[2].isdigit() and parts[3].isdigit():
            base = f"{parts[0]}-{parts[1]}-{parts[2]}.{parts[3]}"
            if base in MODEL_PRICING_USD_PER_MILLION:
                return base

    # Direct alias map.
    if normalized in MODEL_NAME_ALIASES:
        return MODEL_NAME_ALIASES[normalized]

    # Exact or prefix match against the priced table.
    for priced in MODEL_PRICING_USD_PER_MILLION:
        if normalized == priced or normalized.startswith(priced + "-"):
            return priced

    return None


def compute_cost_usd(
    model_name: Optional[str],
    input_tokens: int,
    output_tokens: int,
    cache_tokens: int = 0,
) -> Optional[float]:
    """Look up pricing for ``model_name`` and return USD cost (or None).

    Returns ``None`` if the model isn't in the pricing table -- callers
    should treat that as "unknown" rather than free.
    """
    canonical = canonicalize_model_name(model_name)
    if canonical is None:
        return None
    pricing = MODEL_PRICING_USD_PER_MILLION.get(canonical)
    if pricing is None:
        return None
    return round(
        (input_tokens * pricing["input"]
         + output_tokens * pricing["output"]
         + cache_tokens * pricing["cache"]) / 1_000_000,
        6,
    )


# ---------------------------------------------------------------------------
# Report
# ---------------------------------------------------------------------------


@dataclass
class CostReport:
    # ----- Coarse counters (always populated; legacy) -----
    n_llm_calls_estimate: int = 0
    n_decisions: int = 0
    llm_calls_per_task: float = 0.0
    llm_calls_per_successful_task: float = 0.0
    cost_adjusted_evaluation_sr: float = 0.0

    # ----- Agent-side actuals (from trajectory.json final_metrics) -----
    agent_total_cost_usd: float = 0.0
    agent_input_tokens: int = 0
    agent_output_tokens: int = 0
    agent_cache_tokens: int = 0
    agent_cost_per_task_usd: float = 0.0
    agent_cost_source_breakdown: dict[str, int] = field(default_factory=dict)

    # ----- Host-side actuals (from LiteLLMClient instances) -----
    host_total_cost_usd: float = 0.0
    host_input_tokens: int = 0
    host_output_tokens: int = 0
    host_cache_tokens: int = 0
    host_cost_by_tag: dict[str, float] = field(default_factory=dict)

    # ----- Combined headline numbers -----
    total_cost_usd: float = 0.0
    total_cost_per_task_usd: float = 0.0
    total_cost_per_successful_task_usd: float = 0.0


def compute_cost(
    *,
    event_counts: dict[str, int],
    n_tasks_attempted: int,
    n_tasks_passed: int,
    evaluation_sr: float,
    replay_records: Optional[Iterable] = None,
    host_clients: Optional[Iterable] = None,
) -> CostReport:
    """Aggregate cost-related metrics.

    Parameters
    ----------
    event_counts
        Counts from EventStore for ``patch_proposed`` / ``patch_applied`` /
        ``patch_rejected`` / ``trial_ended_learning``.
    n_tasks_attempted, n_tasks_passed, evaluation_sr
        Same as before -- coarse counter denominators.
    replay_records
        ReplayRecords for the run; their ``outcome.cost_usd``,
        ``outcome.n_input_tokens`` etc are summed into the agent-side
        totals. ``None`` -> agent-side totals stay at 0.
    host_clients
        Iterable of ``LiteLLMClient`` instances (the ones the runtime built
        for SkillAuthor / LLMSelfRetriever). Each contributes its
        cumulative tokens + cost. ``None`` -> host-side stays at 0.
    """
    rep = CostReport()

    # ----- Coarse counters (legacy) -----
    n_proposed = int(event_counts.get("patch_proposed", 0))
    n_decisions = int(event_counts.get("trial_ended_learning", 0))
    rep.n_decisions = n_decisions
    rep.n_llm_calls_estimate = n_proposed
    if n_tasks_attempted > 0:
        rep.llm_calls_per_task = rep.n_llm_calls_estimate / n_tasks_attempted
    if n_tasks_passed > 0:
        rep.llm_calls_per_successful_task = (
            rep.n_llm_calls_estimate / n_tasks_passed
        )

    # ----- Agent-side (from ReplayRecords) -----
    if replay_records is not None:
        source_counts: dict[str, int] = {}
        for r in replay_records:
            o = getattr(r, "outcome", None)
            if o is None:
                continue
            rep.agent_input_tokens  += int(getattr(o, "n_input_tokens", 0) or 0)
            rep.agent_output_tokens += int(getattr(o, "n_output_tokens", 0) or 0)
            rep.agent_cache_tokens  += int(getattr(o, "n_cache_tokens", 0) or 0)
            rep.agent_total_cost_usd += float(getattr(o, "cost_usd", 0.0) or 0.0)
            src = getattr(o, "cost_source", "") or "unknown"
            source_counts[src] = source_counts.get(src, 0) + 1
        rep.agent_cost_source_breakdown = source_counts
        if n_tasks_attempted > 0:
            rep.agent_cost_per_task_usd = rep.agent_total_cost_usd / n_tasks_attempted

    # ----- Host-side (from LiteLLMClient.cumulative_*) -----
    if host_clients is not None:
        for c in host_clients:
            tag = getattr(c, "_tag", "host_llm")
            n_in = int(getattr(c, "_n_input_tokens", 0) or 0)
            n_out = int(getattr(c, "_n_output_tokens", 0) or 0)
            n_cache = int(getattr(c, "_n_cache_tokens", 0) or 0)
            usd = compute_cost_usd(
                getattr(c, "model", None), n_in, n_out, n_cache,
            ) or 0.0
            rep.host_input_tokens  += n_in
            rep.host_output_tokens += n_out
            rep.host_cache_tokens  += n_cache
            rep.host_total_cost_usd += usd
            rep.host_cost_by_tag[tag] = rep.host_cost_by_tag.get(tag, 0.0) + usd
        # Round to a sensible cents-level precision.
        rep.host_total_cost_usd = round(rep.host_total_cost_usd, 6)
        rep.host_cost_by_tag = {
            k: round(v, 6) for k, v in rep.host_cost_by_tag.items()
        }

    # ----- Combined headline -----
    rep.total_cost_usd = round(rep.agent_total_cost_usd + rep.host_total_cost_usd, 6)
    if n_tasks_attempted > 0:
        rep.total_cost_per_task_usd = round(
            rep.total_cost_usd / n_tasks_attempted, 6
        )
    if n_tasks_passed > 0:
        rep.total_cost_per_successful_task_usd = round(
            rep.total_cost_usd / n_tasks_passed, 6
        )

    # ----- Cost-adjusted SR (legacy proxy) -----
    if rep.n_llm_calls_estimate > 0:
        rep.cost_adjusted_evaluation_sr = evaluation_sr / rep.n_llm_calls_estimate
    else:
        rep.cost_adjusted_evaluation_sr = evaluation_sr

    return rep


__all__ = [
    "CostReport",
    "compute_cost",
    "compute_cost_usd",
    "canonicalize_model_name",
    "MODEL_PRICING_USD_PER_MILLION",
]
