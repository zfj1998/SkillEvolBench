"""Pydantic schemas for SkillEvolBench static assets and runtime config."""

# Part 1 (static assets)
from skillevolbench.schemas.task import (
    TaskSpec,
    SkillFamilyMeta,
    TaskRole,
    TaskPhase,
    CompositionType,
    DomainGroup,
    HarborPaths,
    ENV_TO_DOMAIN,
    ROLE_TO_INDEX,
    ROLE_TO_PHASE,
)

# Part 3 (runtime configs)
from skillevolbench.schemas.baseline import (
    BaselineConfig,
    Track,
    FeedbackLevel,
    SkillInit,
    RevisionTrigger,
    DefaultStrategy,
)
from skillevolbench.schemas.strategy import (
    StrategyConfig,
    StrategyName,
    CandidateMode,
)
from skillevolbench.schemas.run import (
    RunConfig,
    EnvOrders,
    LLMDefaults,
    HarborOrchestratorType,
    OrderSeed,
    EnvironmentId,
)

# Part 5 (skill / replay / event / retrieval)
from skillevolbench.schemas.skill import (
    SkillStatus,
    OperationType,
    AuthorStrategy,
    Applicability,
    SkillEvidence,
    SkillVersionRecord,
    SkillManifestEntry,
    SkillVersion,
    SkillPatch,
    ApplyResult,
    LibraryManifest,
)
from skillevolbench.schemas.replay import (
    FailedTest,
    RubricDimension,
    TrialOutcome,
    CompactedTrajectory,
    ReplayRecord,
)
from skillevolbench.schemas.retrieval import (
    RetrievedSkill,
    RetrievalResult,
    RetrievalEvent,
)
from skillevolbench.schemas.event import (
    LifecycleEventType,
    PatchEventType,
    SystemEventType,
    EVENT_PREFIX_TO_CHANNEL,
    DEFAULT_CHANNEL,
)


__all__ = [
    # Part 1
    "TaskSpec",
    "SkillFamilyMeta",
    "TaskRole",
    "TaskPhase",
    "CompositionType",
    "DomainGroup",
    "HarborPaths",
    "ENV_TO_DOMAIN",
    "ROLE_TO_INDEX",
    "ROLE_TO_PHASE",
    # Part 3
    "BaselineConfig",
    "Track",
    "FeedbackLevel",
    "SkillInit",
    "RevisionTrigger",
    "DefaultStrategy",
    "StrategyConfig",
    "StrategyName",
    "CandidateMode",
    "RunConfig",
    "EnvOrders",
    "LLMDefaults",
    "HarborOrchestratorType",
    "OrderSeed",
    "EnvironmentId",
    # Part 5: skill
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
    # Part 5: replay
    "FailedTest",
    "RubricDimension",
    "TrialOutcome",
    "CompactedTrajectory",
    "ReplayRecord",
    # Part 5: retrieval
    "RetrievedSkill",
    "RetrievalResult",
    "RetrievalEvent",
    # Part 5: event
    "LifecycleEventType",
    "PatchEventType",
    "SystemEventType",
    "EVENT_PREFIX_TO_CHANNEL",
    "DEFAULT_CHANNEL",
]
