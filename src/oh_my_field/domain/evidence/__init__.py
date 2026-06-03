"""Domain view: Evidence records and the captured-work primitives they aggregate.

Re-exported from oh_my_field.domain.models so callers can import by
concept (the models share frozen base primitives, so they live in one
definition module to avoid cross-concept import cycles).
"""

from oh_my_field.domain.models import (
    ArtifactStorageMode,
    CapturedFileRole,
    CapturedTextFile,
    CaptureStatus,
    CommandEnvPolicy,
    CommandExecution,
    CommandRiskCategory,
    ContextSource,
    ContextSourceType,
    CostMetrics,
    EvidenceRecord,
    FieldFailureHistory,
    FieldManifest,
    FieldPolicy,
    FieldPreference,
    FieldQualityBar,
    HarnessResult,
    HarnessStatus,
    LatencyMetrics,
    NetworkPolicy,
    SuccessLabel,
    TaskOutcome,
    ToolCallRecord,
)

__all__ = [
    "ArtifactStorageMode",
    "CaptureStatus",
    "CapturedFileRole",
    "CapturedTextFile",
    "CommandEnvPolicy",
    "CommandExecution",
    "CommandRiskCategory",
    "ContextSource",
    "ContextSourceType",
    "CostMetrics",
    "EvidenceRecord",
    "FieldFailureHistory",
    "FieldManifest",
    "FieldPolicy",
    "FieldPreference",
    "FieldQualityBar",
    "HarnessResult",
    "HarnessStatus",
    "LatencyMetrics",
    "NetworkPolicy",
    "SuccessLabel",
    "TaskOutcome",
    "ToolCallRecord",
]
