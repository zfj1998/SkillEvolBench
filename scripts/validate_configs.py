"""Validate yaml files under ``configs/`` against benchmark schemas.

The validator checks every baseline and strategy yaml, verifies that required
canonical baseline configs are present, and confirms that each baseline's
``default_strategy`` resolves to a strategy yaml or ``none``.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from pydantic import ValidationError

from skillevolbench.schemas import (  # noqa: E402
    BaselineConfig,
    StrategyConfig,
    EnvOrders,
    LLMDefaults,
)


@dataclass
class ConfigReport:
    n_baselines: int = 0
    n_strategies: int = 0
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.errors

    def fail(self, msg: str) -> None:
        self.errors.append(msg)

    def warn(self, msg: str) -> None:
        self.warnings.append(msg)


_REQUIRED_BASELINES = {
    "no_skill",
    "raw_trajectory_rag",
    "selfgen_zero_shot",
    "selfgen_experience_always",
    "curated_static",
    "curated_with_revision_always",
}

_EXPECTED_STRATEGIES = {"chain", "chain_tier3"}


def validate_configs(configs_root: Path) -> ConfigReport:
    rep = ConfigReport()
    if not configs_root.exists():
        rep.fail(f"configs/ not found at {configs_root}")
        return rep

    baselines: dict[str, BaselineConfig] = {}
    bl_dir = configs_root / "baselines"
    if not bl_dir.exists():
        rep.fail("configs/baselines/ not found")
        return rep
    for f in sorted(bl_dir.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        try:
            bl = BaselineConfig.from_yaml(f)
        except ValidationError as e:
            rep.fail(f"{f}: {_format_validation_error(e)}")
            continue
        if bl.name != f.stem:
            rep.fail(
                f"{f.name}: yaml 'name' field {bl.name!r} does not equal "
                f"file stem {f.stem!r}"
            )
            continue
        if bl.name in baselines:
            rep.fail(f"{f}: duplicate baseline name {bl.name!r}")
            continue
        baselines[bl.name] = bl
    rep.n_baselines = len(baselines)

    missing = _REQUIRED_BASELINES - set(baselines)
    if missing:
        rep.fail(f"missing required baselines: {sorted(missing)}")
    optional = set(baselines) - _REQUIRED_BASELINES
    if optional:
        rep.warn(f"optional baseline configs present: {sorted(optional)}")

    strategies: dict[str, StrategyConfig] = {}
    st_dir = configs_root / "strategies"
    if not st_dir.exists():
        rep.fail("configs/strategies/ not found")
        return rep
    for f in sorted(st_dir.glob("*.yaml")):
        if f.name.startswith("_"):
            continue
        try:
            st = StrategyConfig.from_yaml(f)
        except ValidationError as e:
            rep.fail(f"{f}: {_format_validation_error(e)}")
            continue
        if st.name != f.stem:
            rep.fail(f"{f.name}: yaml 'name' {st.name!r} != file stem {f.stem!r}")
            continue
        strategies[st.name] = st
    rep.n_strategies = len(strategies)

    extra = set(strategies) - _EXPECTED_STRATEGIES
    missing = _EXPECTED_STRATEGIES - set(strategies)
    if missing:
        rep.fail(f"missing strategies: {sorted(missing)}")
    if extra:
        rep.warn(f"extra strategies: {sorted(extra)}")

    for bl_name, bl in baselines.items():
        if bl.default_strategy == "none":
            continue
        if bl.default_strategy not in strategies:
            rep.fail(
                f"baseline {bl_name!r}.default_strategy={bl.default_strategy!r} "
                f"has no matching configs/strategies/{bl.default_strategy}.yaml"
            )

    eo_path = configs_root / "env_orders.yaml"
    if not eo_path.exists():
        rep.fail(f"missing {eo_path}")
    else:
        try:
            EnvOrders.from_yaml(eo_path)
        except ValidationError as e:
            rep.fail(f"{eo_path}: {_format_validation_error(e)}")

    llm_path = configs_root / "llm.yaml"
    if not llm_path.exists():
        rep.fail(f"missing {llm_path}")
    else:
        try:
            LLMDefaults.from_yaml(llm_path)
        except ValidationError as e:
            rep.fail(f"{llm_path}: {_format_validation_error(e)}")

    return rep


def _format_validation_error(exc: ValidationError) -> str:
    """Render a ValidationError as a concise single-line message."""
    lines = []
    for err in exc.errors():
        loc = ".".join(str(p) for p in err["loc"])
        lines.append(f"[{loc or '<root>'}] {err['msg']}")
    return "; ".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--configs-root", type=Path, default=REPO_ROOT / "configs")
    args = p.parse_args(argv)

    rep = validate_configs(args.configs_root)

    if rep.errors:
        print(f"x {len(rep.errors)} error(s):")
        for e in rep.errors:
            print(f"   - {e}")
    if rep.warnings:
        print(f"! {len(rep.warnings)} warning(s):")
        for w in rep.warnings:
            print(f"   - {w}")
    print(
        f"Summary: {rep.n_baselines} baseline config(s), "
        f"{rep.n_strategies}/{len(_EXPECTED_STRATEGIES)} strategies "
        f"({'PASS' if rep.ok else 'FAIL'})"
    )
    return 0 if rep.ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
