"""LifecycleMaintainer -- post-eval retire / quarantine / narrow (Part 6 §6.6).

Runs once per environment transition, after the eval block has been scored.
The score-before-maintain rule (§9 of design doc) means: the *current*
environment's eval scores are already locked in, and only *future*
environments are affected by the maintenance decisions.

Triggers:

* aggregate skill-level evidence from the env's :class:`ReplayRecord`s
* skills with high harm score (failure / use ratio) -> retire
* skills failing only in narrow contexts -> narrow applicability
* ambiguous skills below retirement threshold -> quarantine

Decisions are deterministic given the same eval records + thresholds.
Patches go through the LibraryStore (NOT through FreezeController, since
freeze has already been lifted by the time maintenance runs).

This implementation is intentionally LLM-free: the per-skill statistics
above + simple thresholds give us reproducible ablation comparisons.
"""

from __future__ import annotations

import logging
import uuid
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Optional

from skillevolbench.schemas import (
    AuthorStrategy,
    OperationType,
    ReplayRecord,
    SkillPatch,
    SkillStatus,
)


_LOG = logging.getLogger(__name__)


@dataclass
class _SkillEvidence:
    skill_id: str
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    failure_contexts: list[dict[str, Any]] = field(default_factory=list)

    @property
    def harm_score(self) -> float:
        if self.use_count == 0:
            return 0.0
        return self.failure_count / self.use_count


@dataclass
class MaintenanceConfig:
    retire_harm_threshold: float = 0.7      # >0.7 -> retire
    quarantine_harm_threshold: float = 0.4  # 0.4-0.7 -> quarantine
    min_use_for_decision: int = 3           # never retire on <3 uses
    narrow_when_failures_in_one_env_only: bool = True


class LifecycleMaintainer:
    """Threshold-based post-eval skill maintenance."""

    def __init__(
        self,
        library: Any,
        event_store: Any,
        config: Optional[MaintenanceConfig] = None,
    ) -> None:
        self.library = library
        self.event_store = event_store
        self.config = config or MaintenanceConfig()

    def run(self, env_id: str, eval_records: list[ReplayRecord]) -> dict[str, Any]:
        """Score skills, then issue retire / quarantine / narrow patches.

        Returns a summary dict for the env_transition log.
        """
        stats = self._aggregate(eval_records)
        retired: list[str] = []
        quarantined: list[str] = []
        narrowed: list[str] = []

        for skill_id, stat in stats.items():
            if stat.use_count < self.config.min_use_for_decision:
                continue
            if stat.harm_score >= self.config.retire_harm_threshold:
                self._retire(skill_id, stat, env_id)
                retired.append(skill_id)
            elif stat.harm_score >= self.config.quarantine_harm_threshold:
                self._quarantine(skill_id, stat, env_id)
                quarantined.append(skill_id)
            elif (
                self.config.narrow_when_failures_in_one_env_only
                and self._failures_concentrated_in_one_env(stat)
            ):
                self._narrow(skill_id, stat, env_id)
                narrowed.append(skill_id)

        summary = {
            "env_id": env_id,
            "n_retired": len(retired),
            "n_quarantined": len(quarantined),
            "n_narrowed": len(narrowed),
            "retired": retired,
            "quarantined": quarantined,
            "narrowed": narrowed,
        }
        self.event_store.record("maintenance_completed", summary)
        return summary

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    @staticmethod
    def _aggregate(records: list[ReplayRecord]) -> dict[str, _SkillEvidence]:
        out: dict[str, _SkillEvidence] = {}
        for r in records:
            for sid in r.skills_actually_used:
                ev = out.setdefault(sid, _SkillEvidence(skill_id=sid))
                ev.use_count += 1
                if r.outcome.verifier_passed:
                    ev.success_count += 1
                else:
                    ev.failure_count += 1
                    ev.failure_contexts.append({
                        "env": r.env_id,
                        "family": r.family_id,
                        "task": r.task_id,
                        "task_role": r.task_role,
                        "failure_summary": r.outcome.failure_summary,
                    })
        return out

    @staticmethod
    def _failures_concentrated_in_one_env(stat: _SkillEvidence) -> bool:
        if stat.failure_count < 2:
            return False
        envs = {ctx.get("env") for ctx in stat.failure_contexts}
        return len(envs) == 1

    # ------------------------------------------------------------------
    # Action helpers (each issues one patch via LibraryStore.apply_patch)
    # ------------------------------------------------------------------

    def _retire(self, skill_id: str, stat: _SkillEvidence, env_id: str) -> None:
        if not self.library.has_skill(skill_id):
            return
        from skillevolbench.stores.library_store import skill_id_to_slug
        slug = skill_id_to_slug(skill_id)
        patch = SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=f"Retire {skill_id} (harm={stat.harm_score:.2f}, "
                    f"uses={stat.use_count})",
            upsert_files={},
            delete_paths=[slug],          # filesystem-level slug
            target_skill_ids=[skill_id],   # formal latent_skill_id
            operation_type=OperationType.RETIRE,
            triggered_by_task=f"maintenance_after_{env_id}",
        )
        try:
            result = self.library.apply_patch(
                patch,
                current_task=f"maintenance_after_{env_id}",
                strategy_name=AuthorStrategy.LIFECYCLE_MAINTAINER.value,
            )
            self.event_store.record(
                "skill_retired",
                {
                    "skill_id": skill_id,
                    "harm_score": stat.harm_score,
                    "uses": stat.use_count,
                    "commit": result.commit_hash,
                },
            )
        except PermissionError:
            # Library is frozen -- shouldn't happen because maintainer runs
            # after unfreeze. Log and move on.
            _LOG.warning(
                "LifecycleMaintainer: cannot retire %s while frozen", skill_id
            )

    def _quarantine(self, skill_id: str, stat: _SkillEvidence, env_id: str) -> None:
        if not self.library.has_skill(skill_id):
            return
        # Read current entry, flip status, write a tiny update via apply_patch
        # whose only effect is to bump the manifest. We do this by writing
        # the same SKILL.md content back -- the manifest update side effect
        # is what we want.
        ver = self.library.get_skill(skill_id)
        skill_md = ver.files.get("SKILL.md", "")
        patch = SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=f"Quarantine {skill_id} (harm={stat.harm_score:.2f})",
            upsert_files={f"{skill_id}/SKILL.md": skill_md},
            target_skill_ids=[skill_id],
            operation_type=OperationType.QUARANTINE,
            triggered_by_task=f"maintenance_after_{env_id}",
        )
        try:
            result = self.library.apply_patch(
                patch,
                current_task=f"maintenance_after_{env_id}",
                strategy_name=AuthorStrategy.LIFECYCLE_MAINTAINER.value,
            )
        except PermissionError:
            return
        # Flip status in manifest by rewriting it directly. The apply_patch
        # set status=ACTIVE; we override to QUARANTINED. A fresh commit (not
        # amend) keeps the upstream apply_patch hash reachable.
        #
        # Also unlink the skill directory from the working tree -- under
        # native skill auto-discovery (Harbor 0.6+ env.py mounts
        # ``library/active/`` into ``~/.claude/skills/`` etc.) the agent
        # would otherwise still surface QUARANTINED skills via Tier-1
        # description loading because native discovery scans the directory
        # rather than the manifest. Git history is preserved either way.
        manifest = self.library._load_manifest()
        if skill_id in manifest.skills:
            manifest.skills[skill_id].status = SkillStatus.QUARANTINED
            self.library._save_manifest(manifest)
            from skillevolbench.stores.library_store import skill_id_to_slug
            slug = skill_id_to_slug(skill_id)
            skill_dir = self.library.active_dir / slug
            if skill_dir.exists():
                import shutil
                shutil.rmtree(skill_dir)
            self.library._git.add_all()
            self.library._git.commit(
                f"manifest: quarantine {skill_id} (harm={stat.harm_score:.2f})"
            )
        self.event_store.record(
            "skill_quarantined",
            {
                "skill_id": skill_id,
                "harm_score": stat.harm_score,
                "uses": stat.use_count,
                "commit": result.commit_hash,
            },
        )

    def _narrow(self, skill_id: str, stat: _SkillEvidence, env_id: str) -> None:
        if not self.library.has_skill(skill_id):
            return
        # Mutate manifest's applicability entry directly. This does not
        # change skill files but does change the manifest -- a fresh patch
        # commit captures it.
        ver = self.library.get_skill(skill_id)
        skill_md = ver.files.get("SKILL.md", "")
        bad_envs = sorted({ctx.get("env") for ctx in stat.failure_contexts if ctx.get("env")})
        patch = SkillPatch(
            patch_id=str(uuid.uuid4()),
            summary=f"Narrow {skill_id} (exclude={bad_envs})",
            upsert_files={f"{skill_id}/SKILL.md": skill_md},
            target_skill_ids=[skill_id],
            operation_type=OperationType.NARROW,
            triggered_by_task=f"maintenance_after_{env_id}",
        )
        try:
            result = self.library.apply_patch(
                patch,
                current_task=f"maintenance_after_{env_id}",
                strategy_name=AuthorStrategy.LIFECYCLE_MAINTAINER.value,
            )
        except PermissionError:
            return
        manifest = self.library._load_manifest()
        if skill_id in manifest.skills:
            entry = manifest.skills[skill_id]
            for env in bad_envs:
                if env not in entry.applicability.exclude:
                    entry.applicability.exclude.append(env)
            self.library._save_manifest(manifest)
            self.library._git.add_all()
            # Fresh commit (no amend) -- see _quarantine for rationale.
            self.library._git.commit(
                f"manifest: narrow {skill_id} (exclude={bad_envs})"
            )
        self.event_store.record(
            "applicability_narrowed",
            {
                "skill_id": skill_id,
                "excluded_envs": bad_envs,
                "commit": result.commit_hash,
            },
        )


__all__ = ["LifecycleMaintainer", "MaintenanceConfig"]
