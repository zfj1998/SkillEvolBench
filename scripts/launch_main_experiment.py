"""Launch the canonical baseline set.

Outer parallelism: one ``LifelongRunner.run`` subprocess per baseline/rep.
Inner concurrency: each baseline's Harbor Job runs ``n_concurrent_trials=1``
(lifelong protocol hard requirement). So the actual parallelism limit is
``min(max_workers, len(baselines))``.

Each subprocess invokes ``python -m scripts.run`` with the baseline yaml,
inheriting environment variables (incl. API keys). Failures in one
baseline don't take down the others -- a final summary lists the
exit codes.

Usage::

    python -m scripts.launch_main_experiment --order-seed A --max-workers 4

    # Subset of baselines:
    python -m scripts.launch_main_experiment --baselines no_skill,selfgen_experience

    # Dry-run (print commands only):
    python -m scripts.launch_main_experiment --dry-run
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
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from skillevolbench.baselines import CANONICAL_BASELINES


_LOG = logging.getLogger(__name__)


def _build_command(
    baseline_name: str,
    *,
    order_seed: str,
    workspace_root: Path,
    rep_index: Optional[int] = None,
    run_id: Optional[str] = None,
) -> list[str]:
    cmd = [
        sys.executable, "-m", "scripts.run",
        "--baseline-name", baseline_name,
        "--order-seed", order_seed,
        "--workspace-root", str(workspace_root),
    ]
    if run_id is not None:
        cmd.extend(["--run-id", run_id])
    return cmd


def _make_rep_run_id(
    baseline_name: str, order_seed: str, rep_index: int
) -> str:
    """Stable run_id for the i-th replicate; bypasses the timestamp-based
    auto-generator so 3 reps launched in the same minute don't collide."""
    return f"{baseline_name}__seed{order_seed}__rep{rep_index}"


def _run_one(
    baseline_name: str,
    *,
    order_seed: str,
    workspace_root: Path,
    rep_index: int,
    run_id: str,
) -> tuple[str, int, int, float]:
    """Subprocess wrapper for one (baseline, rep). Returns (name, rep, rc, dt)."""
    cmd = _build_command(
        baseline_name=baseline_name,
        order_seed=order_seed,
        workspace_root=workspace_root,
        rep_index=rep_index,
        run_id=run_id,
    )
    t0 = time.monotonic()
    proc = subprocess.run(cmd, check=False)
    return baseline_name, rep_index, proc.returncode, time.monotonic() - t0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--order-seed", default="A", choices=["A", "B", "C"])
    p.add_argument("--workspace-root", type=Path, default=Path("workspace/runs"))
    p.add_argument("--max-workers", type=int, default=4,
                   help="number of baselines (× reps) to run in parallel")
    p.add_argument("--baselines", default=None,
                   help="comma-separated subset of canonical baselines "
                        "(default: all canonical)")
    p.add_argument("--n-reps", type=int, default=1,
                   help="number of replicate runs per baseline. Each rep "
                        "uses the same order-seed but a distinct run_id "
                        "(<baseline>__seed<seed>__rep<i>); variance therefore "
                        "comes from LLM nondeterminism alone, not task order.")
    p.add_argument("--dry-run", action="store_true",
                   help="print commands without executing")
    args = p.parse_args(argv)

    if args.n_reps < 1:
        raise SystemExit(f"--n-reps must be >= 1, got {args.n_reps}")

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(name)s %(message)s",
    )

    if args.baselines:
        names = [b.strip() for b in args.baselines.split(",") if b.strip()]
        unknown = [b for b in names if b not in CANONICAL_BASELINES]
        if unknown:
            raise SystemExit(
                f"Unknown baselines: {unknown}. "
                f"Canonical: {list(CANONICAL_BASELINES)}"
            )
    else:
        names = list(CANONICAL_BASELINES)

    # Build the full (baseline, rep) job list.
    jobs: list[tuple[str, int, str]] = [
        (n, i, _make_rep_run_id(n, args.order_seed, i))
        for n in names
        for i in range(args.n_reps)
    ]

    if args.dry_run:
        click_eq = "  "
        print(
            f"# launch plan: "
            f"{len(names)} baselines × {args.n_reps} reps = {len(jobs)} runs "
            f"(seed {args.order_seed})"
        )
        for n, rep, run_id in jobs:
            cmd = _build_command(
                n, order_seed=args.order_seed,
                workspace_root=args.workspace_root,
                rep_index=rep, run_id=run_id,
            )
            print(click_eq + shlex.join(cmd))
        return 0

    print(
        f"Launching {len(names)} baselines × {args.n_reps} reps = {len(jobs)} "
        f"runs (max_workers={args.max_workers})..."
    )
    results: list[tuple[str, int, int, float]] = []
    with ProcessPoolExecutor(max_workers=args.max_workers) as ex:
        futures = {
            ex.submit(
                _run_one, n,
                order_seed=args.order_seed,
                workspace_root=args.workspace_root,
                rep_index=rep,
                run_id=run_id,
            ): (n, rep)
            for n, rep, run_id in jobs
        }
        for fut in as_completed(futures):
            name, rep, rc, dt = fut.result()
            status = "OK" if rc == 0 else f"FAIL({rc})"
            print(f"  [{status}] {name} rep={rep}  ({dt:.1f}s)")
            results.append((name, rep, rc, dt))

    n_failed = sum(1 for *_, rc, _ in results if rc != 0)
    print()
    print(f"Launch summary: {len(results) - n_failed}/{len(results)} succeeded")
    if n_failed:
        print("Failed runs:")
        for name, rep, rc, _ in results:
            if rc != 0:
                print(f"  - {name} rep={rep} (exit code {rc})")
    return 0 if n_failed == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
