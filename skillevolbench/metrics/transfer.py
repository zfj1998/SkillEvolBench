"""Transfer, interference, and optional retention metrics.

Captures lifelong-protocol-specific dynamics:

* **Cross-Environment Reuse Rate** -- fraction of trials that successfully
  used a skill from a different environment than the task.
* **Positive / Negative Transfer Rate** -- correctness conditional on
  cross-env reuse.
* **Interference Rate** -- failure attributable to retrieval pulling a wrong
  cross-env skill.
* **Final Retention Rate** -- computed only when a caller supplies replay
  records for that calculation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable, Optional

from skillevolbench.schemas import ReplayRecord


@dataclass
class TransferReport:
    cross_env_reuse_rate: float = 0.0     # trials that used >=1 cross-env skill
    positive_transfer_rate: float = 0.0   # cross-env reuse AND task passed
    negative_transfer_rate: float = 0.0   # cross-env reuse AND task failed
    interference_rate: float = 0.0        # failed AND any retrieved skill is cross-env

    # Optional retention fields; None when no replay records are supplied.
    final_retention_rate: Optional[float] = None
    forgetting_rate: Optional[float] = None
    interference_rate_replay: Optional[float] = None


def compute_transfer(
    *,
    replay_records: Iterable[ReplayRecord],
    retention_replay_records: Optional[Iterable[ReplayRecord]] = None,
    original_records_by_task: Optional[dict[str, ReplayRecord]] = None,
) -> TransferReport:
    """Aggregate transfer + interference + retention.

    Parameters
    ----------
    replay_records
        All records from the main run.
    retention_replay_records
        Optional replay records for final-retention calculations.
    original_records_by_task
        For each retention task_id, the *original* run's record (for
        forgetting comparison).
    """
    records = list(replay_records)
    rep = TransferReport()
    if not records:
        return rep

    # Cross-env reuse: count trials whose actually-used set has any skill
    # whose env id differs from the task's env id.
    n_total = 0
    n_cross_env_reuse = 0
    n_positive = 0
    n_negative = 0
    for r in records:
        n_total += 1
        task_env = r.env_id
        cross = any(
            sid.split("-", 1)[0] != task_env for sid in r.skills_actually_used
        )
        if cross:
            n_cross_env_reuse += 1
            if r.outcome.verifier_passed:
                n_positive += 1
            else:
                n_negative += 1

    if n_total > 0:
        rep.cross_env_reuse_rate = n_cross_env_reuse / n_total
        rep.positive_transfer_rate = n_positive / n_total
        rep.negative_transfer_rate = n_negative / n_total

    # Interference: failed trials with any cross-env retrieval.
    failed = [r for r in records if not r.outcome.verifier_passed]
    if records:
        n_interfered = 0
        for r in failed:
            task_env = r.env_id
            cross = any(
                sid.split("-", 1)[0] != task_env for sid in r.skills_actually_used
            )
            if cross:
                n_interfered += 1
        rep.interference_rate = n_interfered / len(records)

    # Retention replay numbers
    if retention_replay_records is not None:
        replay_list = list(retention_replay_records)
        if replay_list:
            n_pass_replay = sum(1 for r in replay_list if r.outcome.verifier_passed)
            rep.final_retention_rate = n_pass_replay / len(replay_list)

            # Forgetting: originally pass + replay fail
            if original_records_by_task is not None:
                forgot = 0
                counted = 0
                for r in replay_list:
                    orig = original_records_by_task.get(r.task_id)
                    if orig is None:
                        continue
                    if orig.outcome.verifier_passed and not r.outcome.verifier_passed:
                        forgot += 1
                    counted += 1
                if counted > 0:
                    rep.forgetting_rate = forgot / counted

            # Interference in replay (cross-env skill retrieval among failed)
            failed_replay = [r for r in replay_list if not r.outcome.verifier_passed]
            if replay_list:
                n_interfered_replay = sum(
                    1 for r in failed_replay
                    if any(
                        sid.split("-", 1)[0] != r.env_id
                        for sid in r.skills_actually_used
                    )
                )
                rep.interference_rate_replay = n_interfered_replay / len(replay_list)

    return rep


__all__ = ["TransferReport", "compute_transfer"]
