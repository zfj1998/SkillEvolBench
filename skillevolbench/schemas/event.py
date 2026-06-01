"""Audit event schemas.

``EventStore`` writes plain jsonl. This module declares event-type strings and
small optional payload models so downstream readers can validate the audit log
without coupling to writer internals.

Jsonl channels under ``stores/events/``:

* ``lifecycle.jsonl`` -- trial lifecycle, env transitions, freeze/unfreeze
* ``patches.jsonl``   -- patch_proposed / patch_applied / patch_rejected /
                         rollback / noop / candidate_failed
* ``system.jsonl``    -- asset / resume / system events
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field


class LifecycleEventType(str, Enum):
    TRIAL_STARTED = "trial_started"
    TRIAL_ENDED_LEARNING = "trial_ended_learning"
    TRIAL_ENDED_EVAL = "trial_ended_eval"
    TRIAL_ENDED_NO_RESULT = "trial_ended_no_result"
    ORPHAN_TRIAL_ENDED = "orphan_trial_ended"

    CURATED_SEEDED = "curated_seeded"
    ZERO_SHOT_CREATED = "zero_shot_created"
    INDUCTION_DONE = "induction_done"

    LIBRARY_FROZEN = "library_frozen"
    LIBRARY_UNFROZEN = "library_unfrozen"
    PATCH_DISCARDED_IN_FREEZE = "patch_discarded_in_freeze"

    ENV_TRANSITION = "env_transition"

    SKILL_RETIRED = "skill_retired"
    SKILL_QUARANTINED = "skill_quarantined"
    APPLICABILITY_NARROWED = "applicability_narrowed"


class PatchEventType(str, Enum):
    PATCH_PROPOSED = "patch_proposed"
    PATCH_APPLIED = "patch_applied"
    PATCH_REJECTED = "patch_rejected"
    ROLLBACK_DECISION = "rollback_decision"
    NOOP_DECISION = "noop_decision"
    CANDIDATE_FAILED = "candidate_failed"


class SystemEventType(str, Enum):
    ASSET_VALIDATED = "asset_validated"
    RUN_STARTED = "run_started"
    RUN_FINISHED = "run_finished"
    RESUME_DETECTED = "resume_detected"


EVENT_PREFIX_TO_CHANNEL: dict[str, str] = {
    "patch_": "patches",
    "rollback": "patches",
    "noop_": "patches",
    "candidate_": "patches",
    "asset_": "system",
    "run_": "system",
    "resume_": "system",
    "system_": "system",
}
DEFAULT_CHANNEL = "lifecycle"


class _BaseEventPayload(BaseModel):
    model_config = ConfigDict(extra="allow")


class TrialStartedPayload(_BaseEventPayload):
    task_id: str
    role: str
    phase: str
    library_hash: str
    retrieved_skill_ids: list[str] = Field(default_factory=list)


class TrialEndedPayload(_BaseEventPayload):
    task_id: str
    verifier_passed: bool
    reward: Optional[float] = None
    decision_type: Optional[str] = None
    library_hash_after: Optional[str] = None


class PatchEventPayload(_BaseEventPayload):
    patch_id: str
    strategy: str = ""
    summary: str = ""
    target_skill_ids: list[str] = Field(default_factory=list)
    operation_type: str = ""
    triggered_by_task: str = ""
    upsert_paths: list[str] = Field(default_factory=list)
    delete_paths: list[str] = Field(default_factory=list)


class EnvTransitionPayload(_BaseEventPayload):
    from_env: str
    to_env: str
    library_hash: str


__all__ = [
    "LifecycleEventType",
    "PatchEventType",
    "SystemEventType",
    "EVENT_PREFIX_TO_CHANNEL",
    "DEFAULT_CHANNEL",
    "TrialStartedPayload",
    "TrialEndedPayload",
    "PatchEventPayload",
    "EnvTransitionPayload",
]
