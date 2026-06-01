"""Cost estimator for SkillEvolBench runs.

Pricing model: assume each LLM call uses roughly ``avg_tokens_per_call``
tokens total (input + output). Numbers are rough; real cost depends on prompt
length, agent verbosity, and provider pricing.

Usage::

    python -m scripts.estimate_cost \\
        --baseline-name selfgen_experience_always \\
        --strategy chain \\
        --order-seed A
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.baselines import load_baseline
from skillevolbench.schemas import BaselineConfig, StrategyConfig


# ---------------------------------------------------------------------------
# Heuristic pricing (rough; update for your provider)
# ---------------------------------------------------------------------------


# Per-million-token rates ($USD), input + output combined approximate.
# Update from provider docs before billing-sensitive estimates.
_PRICING_USD_PER_M_TOKENS: dict[str, float] = {
    "anthropic/claude-opus-4-5": 22.50,         # avg of $15 in / $75 out at 3:1 ratio
    "anthropic/claude-sonnet-4-5": 6.00,
    "anthropic/claude-haiku-4-5": 1.50,
    "openai/gpt-4o": 7.50,
    "openai/gpt-4o-mini": 0.45,
    "google/gemini-3.1-flash-lite-preview": 0.30,
}


# Rough per-call token budget (in + out). Tunable -- the value is the
# token count we expect each LLM call to consume on average.
_AVG_TOKENS_PER_CALL: dict[str, int] = {
    "agent_trial": 12_000,        # one Harbor agent invocation per task
    "induction": 6_000,           # SkillAuthor.induce_skill (T1)
    "revision": 6_000,            # SkillAuthor.propose
    "zero_shot": 4_000,           # SkillAuthor.zero_shot_create
}


# ---------------------------------------------------------------------------
# Estimator
# ---------------------------------------------------------------------------


@dataclass
class CostEstimate:
    baseline: str
    strategy: str
    order_seed: str

    # Counts
    n_tasks: int = 180
    n_learning_tasks: int = 90        # T1-T3 over 30 families
    n_eval_tasks: int = 90            # T4-T6 over 30 families
    n_zero_shot_calls: int = 0
    n_induction_calls: int = 0
    n_revision_calls: int = 0
    n_selector_calls: int = 0
    n_judge_calls: int = 0

    # Tokens
    agent_tokens: int = 0
    author_tokens: int = 0
    judge_tokens: int = 0

    # USD
    agent_cost_usd: float = 0.0
    author_cost_usd: float = 0.0
    judge_cost_usd: float = 0.0

    @property
    def total_tokens(self) -> int:
        return self.agent_tokens + self.author_tokens + self.judge_tokens

    @property
    def total_cost_usd(self) -> float:
        return self.agent_cost_usd + self.author_cost_usd + self.judge_cost_usd


def estimate_cost(
    *,
    baseline: BaselineConfig,
    strategy: StrategyConfig,
    order_seed: str,
    agent_model: Optional[str] = None,
) -> CostEstimate:
    """Best-effort estimate of token + USD cost for a single 180-task run.

    Assumptions:

    * 30 families, each with 6 tasks; T1-T3 are 'learning', T4-T6 are 'eval'.
    * One agent call per task (no internal multi-step chains).
    * Strategy LLM activity scales with induction and revision settings.

    The estimate is a lower bound; real runs may invoke more calls due to
    retries or fallback chains.
    """
    rep = CostEstimate(
        baseline=baseline.name,
        strategy=strategy.name,
        order_seed=order_seed,
    )

    # ---- 1. Agent calls (one per task) ----
    rep.agent_tokens = rep.n_tasks * _AVG_TOKENS_PER_CALL["agent_trial"]
    agent_model_id = agent_model or baseline.model_name
    rep.agent_cost_usd = _cost_for(rep.agent_tokens, agent_model_id)

    # ---- 2. Strategy / lifecycle LLM calls ----
    if baseline.allow_zero_shot_creation:
        # One zero_shot_create call per family (30 families) on T1.
        rep.n_zero_shot_calls = 30
    if baseline.allow_self_gen_induction:
        # One induce_skill call per family on T1.
        rep.n_induction_calls = 30
    if baseline.allow_revision:
        # Approximate 30 revision attempts over the 30 families. Always-revise
        # baselines may call more often; failures and empty seeds may call less.
        rep.n_revision_calls = 30

    rep.author_tokens = (
        rep.n_zero_shot_calls * _AVG_TOKENS_PER_CALL["zero_shot"]
        + rep.n_induction_calls * _AVG_TOKENS_PER_CALL["induction"]
        + rep.n_revision_calls * _AVG_TOKENS_PER_CALL["revision"]
    )
    rep.judge_tokens = 0

    rep.author_cost_usd = _cost_for(rep.author_tokens, strategy.author_model)
    rep.judge_cost_usd = _cost_for(rep.judge_tokens, strategy.judge_model)
    return rep


def _cost_for(tokens: int, model: str) -> float:
    rate = _PRICING_USD_PER_M_TOKENS.get(model)
    if rate is None:
        return 0.0   # unknown model -> conservatively report 0 (caller is warned)
    return tokens / 1_000_000 * rate


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _format_human(rep: CostEstimate, model: str, strategy: StrategyConfig) -> str:
    out = [
        f"=== Cost estimate ===",
        f"  baseline:           {rep.baseline}",
        f"  strategy:           {rep.strategy}",
        f"  order_seed:         {rep.order_seed}",
        f"  agent model:        {model}",
        f"  author model:       {strategy.author_model}",
        f"  judge model:        {strategy.judge_model}",
        "",
        "## Call breakdown",
        f"  agent trials:       {rep.n_tasks}",
        f"  zero_shot calls:    {rep.n_zero_shot_calls}",
        f"  induction calls:    {rep.n_induction_calls}",
        f"  revision calls:     {rep.n_revision_calls}",
        f"  selector calls:     {rep.n_selector_calls}",
        f"  judge calls:        {rep.n_judge_calls}",
        "",
        "## Tokens (estimated, lower bound)",
        f"  agent:              {rep.agent_tokens:>12,}",
        f"  author:             {rep.author_tokens:>12,}",
        f"  judge:              {rep.judge_tokens:>12,}",
        f"  total:              {rep.total_tokens:>12,}",
        "",
        "## USD cost (estimated, lower bound)",
        f"  agent:              ${rep.agent_cost_usd:.2f}",
        f"  author:             ${rep.author_cost_usd:.2f}",
        f"  judge:              ${rep.judge_cost_usd:.2f}",
        f"  total:              ${rep.total_cost_usd:.2f}",
        "",
        "Notes:",
        "  - Token estimates are coarse averages per call type.",
        "  - Real cost depends on prompt verbosity, retries, and provider pricing.",
        "  - Pricing table is in scripts/estimate_cost.py:_PRICING_USD_PER_M_TOKENS.",
    ]
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline-name", required=True,
                   help="canonical baseline name (e.g. 'selfgen_experience_always')")
    p.add_argument("--strategy", default=None,
                   help="strategy name (default: baseline.default_strategy)")
    p.add_argument("--order-seed", default="A", choices=["A", "B", "C"])
    p.add_argument("--agent-model", default=None,
                   help="override baseline.model_name for agent cost calc")
    p.add_argument("--json", action="store_true")
    args = p.parse_args(argv)

    baseline = load_baseline(args.baseline_name)

    strat_name = args.strategy
    if not strat_name:
        strat_name = baseline.default_strategy
        if strat_name == "none":
            strat_name = "chain"
    strategy = StrategyConfig.from_yaml(
        REPO_ROOT / "configs" / "strategies" / f"{strat_name}.yaml"
    )

    rep = estimate_cost(
        baseline=baseline,
        strategy=strategy,
        order_seed=args.order_seed,
        agent_model=args.agent_model,
    )

    if args.json:
        print(json.dumps(asdict(rep), indent=2))
    else:
        print(_format_human(
            rep,
            model=args.agent_model or baseline.model_name,
            strategy=strategy,
        ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
