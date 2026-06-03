"""Domain view: Cross-runtime export, integrity, and target-validation models.

Re-exported from oh_my_field.domain.models so callers can import by
concept (the models share frozen base primitives, so they live in one
definition module to avoid cross-concept import cycles).
"""

from oh_my_field.domain.models import (
    ArtifactIntegrityLink,
    CapabilityExportBundle,
    ExportStatus,
    ImportStatus,
    IntegrityVerificationCheck,
    IntegrityVerificationResult,
    IntegrityVerificationStatus,
    PortabilityHealth,
    TargetStatusEntry,
    TargetValidationStatus,
)
from oh_my_field.domain.portability.lifecycle import (
    aggregate_target_validation_status,
    build_portability_health,
    normalize_target_validation_status,
)

__all__ = [
    "ArtifactIntegrityLink",
    "CapabilityExportBundle",
    "ExportStatus",
    "ImportStatus",
    "IntegrityVerificationCheck",
    "IntegrityVerificationResult",
    "IntegrityVerificationStatus",
    "PortabilityHealth",
    "TargetStatusEntry",
    "TargetValidationStatus",
    "aggregate_target_validation_status",
    "build_portability_health",
    "normalize_target_validation_status",
]
