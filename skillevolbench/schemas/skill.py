"""Skill and patch schemas.

These are the contracts between revision strategies, authoring components, and
the persistence layer.

Layout of one skill on disk under ``library/active/<skill_id>/``:

::

    <skill_id>/
        SKILL.md              # main instruction (Anthropic SKILL.md format)
        scripts/              # optional executable helpers
        references/           # optional supporting content

The library's ``manifest.yaml`` indexes every skill (active or retired) plus
its full revision history. Every revision is a commit in
``library/.git`` -- the manifest is just a fast index over that history.
"""

from __future__ import annotations

import re
from datetime import datetime, timezone
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator


# ---------------------------------------------------------------------------
# Enums / IDs
# ---------------------------------------------------------------------------


class SkillStatus(str, Enum):
    ACTIVE = "active"
    QUARANTINED = "quarantined"
    RETIRED = "retired"


class OperationType(str, Enum):
    """High-level intent of a SkillPatch.

    The strategy emits one of these; the LibraryStore applies the patch
    atomically (upserts + deletes in one git commit). Multiple operations on
    the same skill within the same patch are allowed (e.g. revise + narrow).
    """

    CREATE = "create"
    REVISE = "revise"
    RETIRE = "retire"
    QUARANTINE = "quarantine"
    NARROW = "narrow"
    REPLACE = "replace"


class AuthorStrategy(str, Enum):
    """Who proposed this version. Used for audit and reports."""

    CURATED_SEED = "curated_seed"
    ZERO_SHOT = "zero_shot"
    INDUCTION = "induction"
    CHAIN = "chain"
    IN_SESSION_REFLECTION = "in_session_reflection"
    LIFECYCLE_MAINTAINER = "lifecycle_maintainer"


# Latent skill IDs match Part 1's task schema (e.g. "E1-LS1.systematic-error-diagnosis").
_LATENT_SKILL_ID_RE = re.compile(r"^E[1-6]-LS[1-5]\.[A-Za-z0-9][A-Za-z0-9_\-]*$")


# ---------------------------------------------------------------------------
# Applicability
# ---------------------------------------------------------------------------


class Applicability(BaseModel):
    """When the skill should / should not be retrieved.

    ``include`` and ``exclude`` are free-form tags (env_id, task_role, regex
    over instruction text). The lifecycle maintainer narrows ``include`` and
    extends ``exclude`` based on observed harm contexts.
    """

    include: list[str] = Field(default_factory=list)
    exclude: list[str] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Manifest entries (the "index" over git history)
# ---------------------------------------------------------------------------


class SkillEvidence(BaseModel):
    """Aggregated stats per skill, updated by hooks + lifecycle maintainer."""

    retrieval_count: int = 0
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    harm_flags: int = 0


class SkillVersionRecord(BaseModel):
    """One row of ``manifest.skills[<id>].versions``."""

    version: int = Field(..., ge=1)
    patch_id: Optional[str] = None
    created_at_task: str = Field(..., description="task_id that triggered this version")
    parent_version: Optional[int] = None
    author_strategy: AuthorStrategy
    git_commit: Optional[str] = None  # populated by LibraryStore.apply_patch
    summary: Optional[str] = None     # one-line summary from the patch


class SkillManifestEntry(BaseModel):
    """One entry of ``manifest.skills``. Indexes everything we know about one
    skill across all of its versions."""

    skill_id: str = Field(..., description="latent_skill_id, e.g. E1-LS1.systematic-error-diagnosis")
    name: str
    family_id: str
    current_version: int = Field(..., ge=1)
    status: SkillStatus = SkillStatus.ACTIVE
    applicability: Applicability = Field(default_factory=Applicability)
    evidence: SkillEvidence = Field(default_factory=SkillEvidence)
    description: Optional[str] = None
    created_at_task: str
    last_revised_at_task: str
    versions: list[SkillVersionRecord] = Field(default_factory=list)

    @field_validator("skill_id")
    @classmethod
    def _check_skill_id(cls, v: str) -> str:
        if not _LATENT_SKILL_ID_RE.match(v):
            raise ValueError(f"skill_id must match E*-LS*.<slug>, got {v!r}")
        return v


# ---------------------------------------------------------------------------
# In-memory skill version (fully-loaded from disk)
# ---------------------------------------------------------------------------


class SkillVersion(BaseModel):
    """One version's complete contents (loaded from
    ``library/active/<skill_id>/`` at a specific git ref)."""

    skill_id: str
    version: int
    files: dict[str, str] = Field(
        default_factory=dict,
        description="path-relative-to-skill-dir -> file contents",
    )
    manifest_entry: Optional[SkillManifestEntry] = None


# ---------------------------------------------------------------------------
# Patches (the unit of evolution)
# ---------------------------------------------------------------------------


class SkillPatch(BaseModel):
    """An atomic, ordered set of upserts + deletes against the library.

    Applied by ``LibraryStore.apply_patch(...)`` as a single git commit.
    Failures roll back the working tree to the prior commit.
    """

    model_config = ConfigDict(use_enum_values=True)

    patch_id: str = Field(..., description="UUID4")
    summary: str = Field(..., description="one-line author intent")

    # Path -> content, relative to ``library/active/``. May span multiple
    # skill directories when, e.g., a refactor splits one skill into two.
    upsert_files: dict[str, str] = Field(default_factory=dict)
    # Paths to delete. Files are not unlinked; the manifest entry's status
    # transitions to RETIRED so git history retains the old version.
    delete_paths: list[str] = Field(default_factory=list)

    target_skill_ids: list[str] = Field(..., min_length=1)
    operation_type: OperationType
    triggered_by_task: str
    triggered_by_failure_type: Optional[str] = None

    # ---- Strategy bookkeeping (set by strategies, not the LLM) ----
    proposing_mode: Optional[str] = None
    attempt_count: int = 1                   # SkillAuthor fallback chain depth

    @field_validator("target_skill_ids")
    @classmethod
    def _check_target_skills(cls, v: list[str]) -> list[str]:
        for sid in v:
            if not _LATENT_SKILL_ID_RE.match(sid):
                raise ValueError(f"target_skill_id {sid!r} is not a valid latent_skill_id")
        return v


# ---------------------------------------------------------------------------
# Apply result
# ---------------------------------------------------------------------------


class ApplyResult(BaseModel):
    """Returned by ``LibraryStore.apply_patch`` after a successful commit."""

    commit_hash: str
    upserted: list[str] = Field(default_factory=list)
    deleted: list[str] = Field(default_factory=list)
    affected_skill_ids: list[str] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ---------------------------------------------------------------------------
# Library-level manifest (the single yaml file at the library root)
# ---------------------------------------------------------------------------


class LibraryManifest(BaseModel):
    """The contents of ``library/manifest.yaml``.

    This is a *git-tracked* file. Every patch updates it then
    ``git add manifest.yaml ...`` + ``git commit``.
    """

    schema_version: int = 1
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    skills: dict[str, SkillManifestEntry] = Field(default_factory=dict)


__all__ = [
    "SkillStatus",
    "OperationType",
    "AuthorStrategy",
    "Applicability",
    "SkillEvidence",
    "SkillVersionRecord",
    "SkillManifestEntry",
    "SkillVersion",
    "SkillPatch",
    "ApplyResult",
    "LibraryManifest",
]
