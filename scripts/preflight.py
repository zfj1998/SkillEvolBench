"""Preflight: aggregated launch gate.

Bundles the checks that should pass before launching a real benchmark run:

1. benchmark assets validate
2. configs validate
3. Harbor SDK is importable
4. ``agent-runtime:latest`` image is present

Exit codes:
  0 - everything green; safe to launch any stage
  1 - asset / config layer broken (must fix before any run)
  2 - Harbor SDK or runtime image missing (dry-runs still work, real runs do not)

Usage::

    python -m scripts.preflight              # report everything
    python -m scripts.preflight --strict     # exit 1 on Harbor / image missing too
    python -m scripts.preflight --json       # machine-readable
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from scripts.validate_assets import validate_all_assets
from scripts.validate_configs import validate_configs


@dataclass
class PreflightReport:
    asset_pass: bool = False
    config_pass: bool = False
    harbor_importable: bool = False
    runtime_image_present: bool = False
    n_asset_errors: int = 0
    n_asset_warnings: int = 0
    n_config_errors: int = 0
    n_canonical_baselines: int = 0
    n_canonical_strategies: int = 0
    asset_error_details: list[str] = field(default_factory=list)
    config_error_details: list[str] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)

    @property
    def core_pass(self) -> bool:
        """Asset + config -- the *minimum* gate for any work."""
        return self.asset_pass and self.config_pass

    @property
    def strict_pass(self) -> bool:
        """Asset + config + Harbor + image -- gate for actual runs."""
        return (
            self.core_pass
            and self.harbor_importable
            and self.runtime_image_present
        )


def _check_harbor() -> bool:
    try:
        import harbor  # noqa: F401
    except ImportError:
        return False
    return True


def _check_runtime_image(tag: str = "agent-runtime:latest") -> bool:
    builder = shutil.which("docker") or shutil.which("podman")
    if not builder:
        return False
    proc = subprocess.run(
        [builder, "image", "inspect", tag],
        capture_output=True, text=True,
    )
    return proc.returncode == 0


def run_preflight(*, strict: bool = False) -> PreflightReport:
    rep = PreflightReport()

    # 1. Asset layer
    asset_rep = validate_all_assets(
        REPO_ROOT / "benchmark" / "skills",
        REPO_ROOT / "benchmark" / "tasks",
        strict_image=False,
    )
    rep.asset_pass = asset_rep.ok
    rep.n_asset_errors = len(asset_rep.errors)
    rep.n_asset_warnings = len(asset_rep.warnings)
    rep.asset_error_details = list(asset_rep.errors)

    # 2. Config layer
    cfg_rep = validate_configs(REPO_ROOT / "configs")
    rep.config_pass = cfg_rep.ok
    rep.n_config_errors = len(cfg_rep.errors)
    rep.n_canonical_baselines = cfg_rep.n_baselines
    rep.n_canonical_strategies = cfg_rep.n_strategies
    rep.config_error_details = list(cfg_rep.errors)

    # 3. Harbor SDK
    rep.harbor_importable = _check_harbor()
    if not rep.harbor_importable:
        rep.notes.append(
            "Harbor SDK is not importable; dry-runs work but real runs "
            "require `pip install harbor`."
        )

    # 4. Runtime image
    rep.runtime_image_present = _check_runtime_image()
    if not rep.runtime_image_present:
        rep.notes.append(
            "agent-runtime:latest is not present in docker/podman; "
            "build it via `docker/agent-build/build.sh` before a real run."
        )

    return rep


def _format_human(rep: PreflightReport, strict: bool) -> str:
    pass_marker = "PASS" if rep.core_pass else "FAIL"
    out = [
        f"=== Preflight ({pass_marker}) ===",
        f"  asset layer:        {'PASS' if rep.asset_pass else 'FAIL'} "
        f"({rep.n_asset_errors} errors, {rep.n_asset_warnings} warnings)",
        f"  config layer:       {'PASS' if rep.config_pass else 'FAIL'} "
        f"({rep.n_canonical_baselines} baseline configs, "
        f"{rep.n_canonical_strategies}/2 strategies)",
        f"  harbor SDK:         {'present' if rep.harbor_importable else 'absent'}",
        f"  agent-runtime:latest: {'present' if rep.runtime_image_present else 'absent'}",
    ]
    if rep.notes:
        out.append("")
        out.append("Notes:")
        for n in rep.notes:
            out.append(f"  - {n}")
    if rep.asset_error_details:
        out.append("")
        out.append("Asset errors:")
        for e in rep.asset_error_details:
            out.append(f"  - {e}")
    if rep.config_error_details:
        out.append("")
        out.append("Config errors:")
        for e in rep.config_error_details:
            out.append(f"  - {e}")
    out.append("")
    if strict:
        out.append(
            f"Strict gate: {'PASS' if rep.strict_pass else 'FAIL'}"
        )
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--strict", action="store_true",
                   help="exit 1 if Harbor SDK or runtime image is missing")
    p.add_argument("--json", action="store_true",
                   help="emit JSON instead of human summary")
    args = p.parse_args(argv)

    rep = run_preflight(strict=args.strict)

    if args.json:
        print(json.dumps(asdict(rep), indent=2))
    else:
        print(_format_human(rep, strict=args.strict))

    if not rep.core_pass:
        return 1
    if args.strict and not rep.strict_pass:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
