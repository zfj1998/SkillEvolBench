"""Static-asset schemas for SkillEvolBench.

Two overlay files extend the existing Harbor task / Anthropic SKILL.md format:

* ``benchmark/skills/<slug>/meta.yaml``  -> ``SkillFamilyMeta``
* ``benchmark/tasks/<slug>/task-spec.yaml`` -> ``TaskSpec``

These overlays add only the SkillEvolBench-specific fields (latent_skill_id,
composition links, phase, trap types, ...). The existing ``task.toml`` and
``SKILL.md`` files are kept as-is (Harbor / Anthropic standard format).

The relationship between the various IDs is:

* ``family_id``        e.g. ``E1-LS1``                   (env id + latent skill index)
* ``slug``             e.g. ``systematic-error-diagnosis`` (folder name in skills/)
* ``latent_skill_id``  e.g. ``E1-LS1.systematic-error-diagnosis``  (composite)
* ``task_id``          e.g. ``E1-LS1-T1``                (logical id in protocol order)
* ``task_slug``        e.g. ``flask-race-condition-500``  (folder name in tasks/)
"""

from __future__ import annotations

import re
from enum import Enum
from pathlib import Path
from typing import List, Optional

from pydantic import BaseModel, Field, field_validator, model_validator


# ---------------------------------------------------------------------------
# Enums and constants
# ---------------------------------------------------------------------------


class TaskRole(str, Enum):
    """The 6 roles inside a skill family.

    The wire spelling matches what the existing ``task.toml`` files already use.
    """

    CANONICAL = "canonical"
    ENRICHED = "enriched"
    VARIANT = "variant"
    CONTEXT_SHIFT = "context-shift"
    ADVERSARIAL = "adversarial"
    COMPOSITION = "composition"


class TaskPhase(str, Enum):
    LEARNING = "learning"
    EVALUATION = "evaluation"


class CompositionType(str, Enum):
    NONE = "none"
    WITHIN_FAMILY = "within_family"
    CROSS_FAMILY = "cross_family"


class DomainGroup(str, Enum):
    """Coarse domain bucket (matches the 6 environments)."""

    CODE_DEBUGGING = "code_debugging"
    TOOL_API_ORCHESTRATION = "tool_api_orchestration"
    DATA_PROCESSING = "data_processing"
    DOCUMENT_PARSING = "document_parsing"
    RESEARCH_SYNTHESIS = "research_synthesis"
    COMMUNICATION_SCHEDULING = "communication_scheduling"


# Wire env-id -> domain bucket. Matches the strings already in task.toml.
ENV_TO_DOMAIN: dict[str, DomainGroup] = {
    "code-debugging-modification": DomainGroup.CODE_DEBUGGING,
    "multi-step-tool-api-orchestration": DomainGroup.TOOL_API_ORCHESTRATION,
    "data-processing-structured-query": DomainGroup.DATA_PROCESSING,
    "document-parsing-extraction-transformation": DomainGroup.DOCUMENT_PARSING,
    "research-information-synthesis": DomainGroup.RESEARCH_SYNTHESIS,
    "communication-scheduling-operations": DomainGroup.COMMUNICATION_SCHEDULING,
}

ENV_SLUG_TO_ID: dict[str, str] = {
    "code-debugging-modification": "E1",
    "multi-step-tool-api-orchestration": "E2",
    "data-processing-structured-query": "E3",
    "document-parsing-extraction-transformation": "E4",
    "research-information-synthesis": "E5",
    "communication-scheduling-operations": "E6",
}

ROLE_TO_INDEX: dict[TaskRole, int] = {
    TaskRole.CANONICAL: 1,
    TaskRole.ENRICHED: 2,
    TaskRole.VARIANT: 3,
    TaskRole.CONTEXT_SHIFT: 4,
    TaskRole.ADVERSARIAL: 5,
    TaskRole.COMPOSITION: 6,
}

ROLE_TO_PHASE: dict[TaskRole, TaskPhase] = {
    TaskRole.CANONICAL: TaskPhase.LEARNING,
    TaskRole.ENRICHED: TaskPhase.LEARNING,
    TaskRole.VARIANT: TaskPhase.LEARNING,
    TaskRole.CONTEXT_SHIFT: TaskPhase.EVALUATION,
    TaskRole.ADVERSARIAL: TaskPhase.EVALUATION,
    TaskRole.COMPOSITION: TaskPhase.EVALUATION,
}


_FAMILY_ID_RE = re.compile(r"^E[1-6]-LS[1-5]$")
_TASK_ID_RE = re.compile(r"^E[1-6]-LS[1-5]-T[1-6]$")
# Slug accepts camelCase too; one historical task is "ts-promise-allSettled-ignored-rejection"
_LATENT_SKILL_ID_RE = re.compile(r"^E[1-6]-LS[1-5]\.[A-Za-z0-9][A-Za-z0-9_\-]*$")
_SLUG_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_\-]*$")


# ---------------------------------------------------------------------------
# Skill family meta.yaml
# ---------------------------------------------------------------------------


class SkillFamilyMeta(BaseModel):
    """Schema of ``benchmark/skills/<slug>/meta.yaml``."""

    schema_version: str = "1.0"

    family_id: str = Field(..., description="E.g. 'E1-LS1'")
    environment_id: str = Field(..., description="E.g. 'E1'")
    latent_skill_id: str = Field(..., description="E.g. 'E1-LS1.systematic-error-diagnosis'")
    slug: str = Field(..., description="Folder name under benchmark/skills/")
    name: str = Field(..., description="Human-readable skill name")
    description: str = Field(..., description="One-sentence description for retrieval")

    # Curated v0 (Path B). Path is relative to the skill folder.
    curated_skill_path: str = "SKILL.md"
    curated_skill_version: str = "1.0"
    curated_skill_author: str = "skillevolbench-team"

    # The 6 task IDs in this family (E*-LS*-T1 .. T6).
    task_ids: List[str] = Field(default_factory=list)

    # Gap definitions (for documentation only; not enforced at runtime).
    gap_1_summary: Optional[str] = None
    gap_2_summary: Optional[str] = None

    @field_validator("family_id")
    @classmethod
    def _check_family_id(cls, v: str) -> str:
        if not _FAMILY_ID_RE.match(v):
            raise ValueError(f"family_id must match E[1-6]-LS[1-5], got {v!r}")
        return v

    @field_validator("environment_id")
    @classmethod
    def _check_env_id(cls, v: str) -> str:
        if v not in {"E1", "E2", "E3", "E4", "E5", "E6"}:
            raise ValueError(f"environment_id must be E1..E6, got {v!r}")
        return v

    @field_validator("latent_skill_id")
    @classmethod
    def _check_latent_id(cls, v: str) -> str:
        if not _LATENT_SKILL_ID_RE.match(v):
            raise ValueError(f"latent_skill_id must match 'E*-LS*.<slug>', got {v!r}")
        return v

    @field_validator("slug")
    @classmethod
    def _check_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(f"slug must be a kebab-case identifier, got {v!r}")
        return v

    @model_validator(mode="after")
    def _check_consistency(self) -> "SkillFamilyMeta":
        if not self.family_id.startswith(self.environment_id + "-"):
            raise ValueError(
                f"family_id {self.family_id!r} must start with environment_id {self.environment_id!r}"
            )
        prefix, _, slug_in_lsid = self.latent_skill_id.partition(".")
        if prefix != self.family_id:
            raise ValueError(
                f"latent_skill_id prefix {prefix!r} != family_id {self.family_id!r}"
            )
        if slug_in_lsid != self.slug:
            raise ValueError(
                f"latent_skill_id slug {slug_in_lsid!r} != slug {self.slug!r}"
            )
        if self.task_ids:
            if len(self.task_ids) != 6:
                raise ValueError(f"task_ids must have length 6, got {len(self.task_ids)}")
            expected = [f"{self.family_id}-T{i}" for i in range(1, 7)]
            if list(self.task_ids) != expected:
                raise ValueError(
                    f"task_ids must be {expected}, got {self.task_ids}"
                )
        return self


# ---------------------------------------------------------------------------
# task-spec.yaml
# ---------------------------------------------------------------------------


class HarborPaths(BaseModel):
    """Sub-paths that point to the existing Harbor task layout."""

    task_toml: str = "task.toml"
    instruction: str = "instruction.md"
    tests: str = "tests/"
    environment: str = "environment/"
    solution: str = "solution/"


class TaskSpec(BaseModel):
    """Schema of ``benchmark/tasks/<slug>/task-spec.yaml``.

    This is a *thin overlay* on top of the existing ``task.toml`` Harbor file.
    It does NOT duplicate fields that already live in ``task.toml [metadata]``
    (those are loaded directly from task.toml). Instead it adds only the
    SkillEvolBench-specific fields needed by the lifelong protocol.
    """

    schema_version: str = "1.0"

    # === Identity (must match task.toml [metadata]) ===
    task_id: str = Field(..., description="E.g. 'E1-LS1-T1'")
    task_slug: str = Field(..., description="Folder name under benchmark/tasks/")
    environment_id: str = Field(..., description="E.g. 'E1'")
    family_id: str = Field(..., description="E.g. 'E1-LS1'")
    latent_skill_id: str = Field(..., description="E.g. 'E1-LS1.systematic-error-diagnosis'")

    # === Role / phase (derived but stored for fast lookup) ===
    task_index: int = Field(..., ge=1, le=6)
    role: TaskRole
    phase: TaskPhase
    within_family_difficulty_rank: int = Field(default=1, ge=1, le=6)

    # === Harbor asset paths (relative to task folder) ===
    harbor: HarborPaths = Field(default_factory=HarborPaths)

    # === Skill linkage ===
    primary_skill: str = Field(..., description="latent_skill_id of the family's primary skill")

    # T6-only fields. Empty for T1-T5.
    required_skills: List[str] = Field(default_factory=list)
    required_skill_compose_order: List[str] = Field(default_factory=list)
    composition_type: CompositionType = CompositionType.NONE

    # T5-only adversarial trap classification (free-form tags).
    trap_types: List[str] = Field(default_factory=list)

    # Reporting bucket (matches the 6 environments).
    domain_group: DomainGroup

    # === Notes ===
    # Optional manual review marker. When auto-generated values for T6 may need
    # human verification, leave a non-empty list of reviewer notes here.
    review_notes: List[str] = Field(default_factory=list)

    # ----- Validators -----

    @field_validator("task_id")
    @classmethod
    def _check_task_id(cls, v: str) -> str:
        if not _TASK_ID_RE.match(v):
            raise ValueError(f"task_id must match E[1-6]-LS[1-5]-T[1-6], got {v!r}")
        return v

    @field_validator("family_id")
    @classmethod
    def _check_family_id(cls, v: str) -> str:
        if not _FAMILY_ID_RE.match(v):
            raise ValueError(f"family_id must match E[1-6]-LS[1-5], got {v!r}")
        return v

    @field_validator("environment_id")
    @classmethod
    def _check_env_id(cls, v: str) -> str:
        if v not in {"E1", "E2", "E3", "E4", "E5", "E6"}:
            raise ValueError(f"environment_id must be E1..E6, got {v!r}")
        return v

    @field_validator("latent_skill_id", "primary_skill")
    @classmethod
    def _check_latent_id(cls, v: str) -> str:
        if not _LATENT_SKILL_ID_RE.match(v):
            raise ValueError(
                f"latent_skill_id must match 'E*-LS*.<slug>', got {v!r}"
            )
        return v

    @field_validator("task_slug")
    @classmethod
    def _check_slug(cls, v: str) -> str:
        if not _SLUG_RE.match(v):
            raise ValueError(f"task_slug must be kebab-case, got {v!r}")
        return v

    @field_validator("required_skills", "required_skill_compose_order")
    @classmethod
    def _check_skill_list(cls, v: List[str]) -> List[str]:
        for sid in v:
            if not _LATENT_SKILL_ID_RE.match(sid):
                raise ValueError(
                    f"skill list entry must be a latent_skill_id, got {sid!r}"
                )
        return v

    @model_validator(mode="after")
    def _check_role_phase(self) -> "TaskSpec":
        # Role -> task_index consistency
        if ROLE_TO_INDEX[self.role] != self.task_index:
            raise ValueError(
                f"role={self.role} expects task_index={ROLE_TO_INDEX[self.role]}, "
                f"got {self.task_index}"
            )
        # Role -> phase consistency
        if ROLE_TO_PHASE[self.role] != self.phase:
            raise ValueError(
                f"role={self.role} expects phase={ROLE_TO_PHASE[self.role]}, "
                f"got {self.phase}"
            )
        # task_id <-> family_id <-> environment_id
        if not self.task_id.startswith(self.family_id + "-T"):
            raise ValueError(
                f"task_id {self.task_id!r} must start with {self.family_id + '-T'!r}"
            )
        if not self.family_id.startswith(self.environment_id + "-"):
            raise ValueError(
                f"family_id {self.family_id!r} must start with {self.environment_id + '-'!r}"
            )
        # T6 must have non-empty required_skills + non-NONE composition_type
        if self.role == TaskRole.COMPOSITION:
            if not self.required_skills:
                raise ValueError(f"{self.task_id}: T6 must specify required_skills")
            if self.composition_type == CompositionType.NONE:
                raise ValueError(f"{self.task_id}: T6 must have composition_type")
            # primary_skill must be in required_skills
            if self.primary_skill not in self.required_skills:
                raise ValueError(
                    f"{self.task_id}: primary_skill {self.primary_skill!r} "
                    f"not in required_skills {self.required_skills}"
                )
            # required_skill_compose_order must be a permutation of required_skills
            if self.required_skill_compose_order:
                if set(self.required_skill_compose_order) != set(self.required_skills):
                    raise ValueError(
                        f"{self.task_id}: required_skill_compose_order does not "
                        f"match required_skills as a set"
                    )
        else:
            if self.required_skills:
                raise ValueError(
                    f"{self.task_id}: only T6 may set required_skills"
                )
            if self.composition_type != CompositionType.NONE:
                raise ValueError(
                    f"{self.task_id}: only T6 may set composition_type"
                )
        # T5 trap types: only T5 may set them
        if self.role != TaskRole.ADVERSARIAL and self.trap_types:
            raise ValueError(
                f"{self.task_id}: only T5 may set trap_types"
            )
        return self

    # ----- Helpers -----

    @classmethod
    def derive_phase(cls, role: TaskRole) -> TaskPhase:
        return ROLE_TO_PHASE[role]

    @classmethod
    def derive_index(cls, role: TaskRole) -> int:
        return ROLE_TO_INDEX[role]

    def harbor_task_dir(self, repo_root: Path) -> Path:
        return repo_root / "benchmark" / "tasks" / self.task_slug

    def instruction_path(self, repo_root: Path) -> Path:
        return self.harbor_task_dir(repo_root) / self.harbor.instruction
