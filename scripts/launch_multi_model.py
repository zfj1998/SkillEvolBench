"""Cartesian launcher: ``baselines × models`` -> N independent runs.

Each (baseline, model) pair becomes one ``python -m scripts.run`` subprocess
with its own ``run_id`` and isolated workspace directory. Failures in one
pair don't take down the others.

Usage::

    # All canonical baselines x all model presets can be expensive.
    skillevolbench launch-multi-model --order-seed A --max-workers 4

    # A targeted slice -- recommended starting point
    skillevolbench launch-multi-model \\
        --baselines selfgen_experience_always,no_skill \\
        --models claude-opus-4.6,gpt-5.4,gemini-3.1-pro,kimi-2.5 \\
        --order-seed A \\
        --max-workers 4

    # Target one model across all baselines
    skillevolbench launch-multi-model \\
        --models claude-sonnet-4.6 \\
        --order-seed A

    # Dry-run (print what would run, no execution)
    skillevolbench launch-multi-model --dry-run

Outer parallelism: ``min(max_workers, total_runs)`` subprocesses.
Inner concurrency: each run forces ``n_concurrent_trials=1`` (lifelong protocol).
LLM rate limits are the practical bottleneck; default ``max_workers=4`` is the
sweet spot on most accounts.
"""

from __future__ import annotations

import argparse
import logging
import shlex
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.baselines import CANONICAL_BASELINES


_LOG = logging.getLogger(__name__)


_MODEL_PRESETS_DIR = REPO_ROOT / "configs" / "models"


def _list_canonical_models() -> list[str]:
    """Return all model preset names (filename stems) in configs/models/."""
    return sorted(p.stem for p in _MODEL_PRESETS_DIR.glob("*.yaml"))


def _build_command(
    baseline_name: str,
    model_name: str,
    *,
    order_seed: str,
    workspace_root: Path,
) -> list[str]:
    model_yaml = _MODEL_PRESETS_DIR / f"{model_name}.yaml"
    return [
        sys.executable, "-m", "scripts.run",
        "--baseline-name", baseline_name,
        "--model-yaml", str(model_yaml),
        "--order-seed", order_seed,
        "--workspace-root", str(workspace_root),
    ]


def _run_one(
    baseline_name: str,
    model_name: str,
    *,
    order_seed: str,
    workspace_root: Path,
) -> tuple[str, str, int, float]:
    """Subprocess wrapper. Returns (baseline, model, returncode, duration_s)."""
    cmd = _build_command(
        baseline_name, model_name,
        order_seed=order_seed,
        workspace_root=workspace_root,
    )
    t0 = time.monotonic()
    proc = subprocess.run(cmd, check=False)
    return baseline_name, model_name, proc.returncode, time.monotonic() - t0


def _validate_models(names: list[str]) -> None:
    available = set(_list_canonical_models())
    unknown = [n for n in names if n not in available]
    if unknown:
        raise SystemExit(
            f"Unknown models: {unknown}\n"
            f"Available presets in {_MODEL_PRESETS_DIR}:\n"
            f"  {sorted(available)}"
        )


def _validate_baselines(names: list[str]) -> None:
    unknown = [n for n in names if n not in CANONICAL_BASELINES]
    if unknown:
        raise SystemExit(
            f"Unknown baselines: {unknown}\n"
            f"Canonical: {list(CANONICAL_BASELINES)}"
        )


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--order-seed", default="A", choices=["A", "B", "C"])
    p.add_argument("--workspace-root", type=Path, default=Path("workspace/runs"))
    p.add_argument("--max-workers", type=int, default=4,
                   help="number of (baseline, model) runs in parallel "
                        "(LLM rate limits typically cap this at 4-6)")
    p.add_argument("--baselines", default=None,
                   help="comma-separated subset of canonical baselines "
                        "(default: all canonical)")
    p.add_argument("--models", default=None,
                   help="comma-separated subset of model preset names "
                        "(default: all model yamls under configs/models/)")
    p.add_argument("--dry-run", action="store_true",
                   help="print commands without executing")
    args = p.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
    )

    # ---- Resolve baselines ----
    if args.baselines:
        baseline_names = [b.strip() for b in args.baselines.split(",") if b.strip()]
        _validate_baselines(baseline_names)
    else:
        baseline_names = list(CANONICAL_BASELINES)

    # ---- Resolve models ----
    if args.models:
        model_names = [m.strip() for m in args.models.split(",") if m.strip()]
        _validate_models(model_names)
    else:
        model_names = _list_canonical_models()

    pairs = [(b, m) for b in baseline_names for m in model_names]

    if args.dry_run:
        print(f"# launch plan: {len(baseline_names)} baselines x "
              f"{len(model_names)} models = {len(pairs)} runs "
              f"(seed {args.order_seed})")
        for b, m in pairs:
            cmd = _build_command(
                b, m,
                order_seed=args.order_seed,
                workspace_root=args.workspace_root,
            )
            print("  " + shlex.join(cmd))
        return 0

    print(
        f"Launching {len(pairs)} runs "
        f"({len(baseline_names)} baselines x {len(model_names)} models, "
        f"max_workers={args.max_workers})..."
    )
    results: list[tuple[str, str, int, float]] = []
    with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {
            ex.submit(
                _run_one, b, m,
                order_seed=args.order_seed,
                workspace_root=args.workspace_root,
            ): (b, m)
            for b, m in pairs
        }
        for fut in as_completed(futures):
            baseline, model, rc, dt = fut.result()
            status = "OK" if rc == 0 else f"FAIL({rc})"
            print(f"  [{status}] {baseline} x {model}  ({dt:.1f}s)")
            results.append((baseline, model, rc, dt))

    n_failed = sum(1 for _, _, rc, _ in results if rc != 0)
    print()
    print(f"Multi-model summary: {len(results) - n_failed}/{len(results)} succeeded")
    if n_failed:
        print("Failed pairs:")
        for baseline, model, rc, _ in results:
            if rc != 0:
                print(f"  - {baseline} x {model} (exit {rc})")
    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
