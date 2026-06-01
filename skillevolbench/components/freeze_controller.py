"""LibraryFreezeController -- score-before-maintain rule (Part 6 §6.5).

The freeze invariant is the protocol's most important guarantee: T4-T6
``library.compute_hash()`` must not change. ``LibraryFreezeController``
implements it with three pieces:

1. ``freeze(env_id)`` -- write the ``.frozen`` marker + cache the current
   hash. Container mounts go readonly via Part 4's ``GlobalLibraryEnvironment``.
2. ``submit_patch(...)`` -- the ONLY allowed write path. Refuses (silently
   queues for audit) when frozen.
3. ``unfreeze_and_maintain(env_id, baseline, eval_records)`` -- assert hash
   unchanged, lift the freeze, optionally trigger ``LifecycleMaintainer``
   for ``allow_post_eval_maintenance`` baselines.

All three protocol invariants are enforced as ``AssertionError``s -- the
hook expects to crash a run rather than silently corrupt the data.
"""

from __future__ import annotations

import logging
from typing import Any, Optional

from skillevolbench.schemas import ApplyResult, SkillPatch


_LOG = logging.getLogger(__name__)


class LibraryFreezeController:
    """Mediates every write to the library + drives env-transition maintenance."""

    def __init__(
        self,
        library: Any,
        event_store: Any,
        maintainer: Optional[Any] = None,
    ) -> None:
        self.library = library
        self.event_store = event_store
        self.maintainer = maintainer  # may be None for non-full-lifecycle baselines

        self.frozen: bool = False
        self.frozen_hash: Optional[str] = None
        self._discarded_patches: list[SkillPatch] = []

    # ------------------------------------------------------------------
    # Freeze / unfreeze
    # ------------------------------------------------------------------

    def freeze(self, env_id: str) -> None:
        if self.frozen:
            # Idempotent: refreeze inside the same env block is a no-op.
            return
        self.frozen_hash = self.library.compute_hash()
        self.library.freeze()
        self.frozen = True
        self.event_store.record(
            "library_frozen",
            {"env_id": env_id, "hash": self.frozen_hash},
        )

    def submit_patch(
        self,
        patch: SkillPatch,
        strategy_name: str,
        current_task: str,
    ) -> Optional[ApplyResult]:
        """Single write API. Returns the apply result, or None when frozen."""
        if self.frozen:
            self._discarded_patches.append(patch)
            self.event_store.record(
                "patch_discarded_in_freeze",
                {"patch_id": patch.patch_id, "task": current_task},
            )
            return None
        result = self.library.apply_patch(patch, current_task, strategy_name)
        # Audit the successful apply.
        self.event_store.record_patch_applied(patch, result, strategy_name)
        return result

    def unfreeze_and_maintain(
        self,
        env_id: str,
        baseline: Any,
        eval_records: list[Any],
    ) -> None:
        """Lift the freeze. Crashes the run if the library was mutated during
        the eval block (the freeze invariant). Optionally runs maintenance."""
        if not self.frozen:
            # Defensive: callers shouldn't unfreeze when not frozen, but we
            # don't want a crash on env transitions where the prev env had
            # no eval block (unusual but legal).
            self._discarded_patches.clear()
            return

        # Hard assert: library hash unchanged.
        current_hash = self.library.compute_hash()
        if current_hash != self.frozen_hash:
            raise AssertionError(
                f"Library hash changed during freeze (env={env_id!r}): "
                f"{current_hash!r} != {self.frozen_hash!r}"
            )

        n_discarded = len(self._discarded_patches)
        self._discarded_patches.clear()

        self.library.unfreeze()
        self.frozen = False
        self.frozen_hash = None
        self.event_store.record(
            "library_unfrozen",
            {"env_id": env_id, "n_patches_discarded": n_discarded},
        )

        # Post-eval maintenance for full-lifecycle baselines only.
        if (
            self.maintainer is not None
            and getattr(baseline, "allow_post_eval_maintenance", False)
        ):
            self.maintainer.run(env_id=env_id, eval_records=eval_records)


__all__ = ["LibraryFreezeController"]
