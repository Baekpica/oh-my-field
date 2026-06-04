"""Compatibility shim for portability workflows and models.

Implementation has moved into domain, application, adapter, and infrastructure
modules. This module preserves the original public import path for CLI and
external callers while the internal code imports layered modules directly.
"""

from oh_my_field.application.portability.adapt_workflow import adapt_capability_package
from oh_my_field.application.portability.export_workflow import (
    export_capability_package,
)
from oh_my_field.application.portability.import_workflow import (
    import_capability_package,
)
from oh_my_field.application.portability.remap_workflow import remap_capability_package
from oh_my_field.application.portability.validate_workflow import (
    validate_capability_package,
)
from oh_my_field.domain.portability.errors import (
    PortabilityAmbiguousTargetError,
    PortabilityBundleExistsError,
    PortabilityBundleParseError,
    PortabilityError,
    PortabilityImportExistsError,
    PortabilityImportNotFoundError,
)
from oh_my_field.domain.portability.models import (
    CapabilityAdaptRequest,
    CapabilityAdaptSummary,
    CapabilityExportRecord,
    CapabilityPortabilityExportRequest,
    CapabilityPortabilityExportSummary,
    CapabilityPortabilityImportRequest,
    CapabilityPortabilityImportSummary,
    CapabilityRemapRequest,
    CapabilityRemapSummary,
    CapabilityValidationRequest,
    CapabilityValidationSummary,
    ContextRemapPlan,
    EvalPassRateComparison,
    EvidenceInclusionMode,
    EvidenceIntegrityProof,
    EvidenceProof,
    EvidenceProvenancePack,
    ExportTarget,
    ImportCollisionPolicy,
    PortabilityAdaptation,
    PortabilityCompatibility,
    PortabilityContextBudget,
    PortabilityManifest,
    PortabilityReadiness,
    PortabilitySource,
    PortabilityTarget,
    PortabilityValidation,
    ProvenanceIntegrity,
    RemapBinding,
    TargetOverlay,
    TargetOverrides,
    TargetRunPlan,
    TargetValidationReport,
    ToolCompatibilityStatus,
    ValidationStatus,
)

__all__ = [
    "CapabilityAdaptRequest",
    "CapabilityAdaptSummary",
    "CapabilityExportRecord",
    "CapabilityPortabilityExportRequest",
    "CapabilityPortabilityExportSummary",
    "CapabilityPortabilityImportRequest",
    "CapabilityPortabilityImportSummary",
    "CapabilityRemapRequest",
    "CapabilityRemapSummary",
    "CapabilityValidationRequest",
    "CapabilityValidationSummary",
    "ContextRemapPlan",
    "EvalPassRateComparison",
    "EvidenceInclusionMode",
    "EvidenceIntegrityProof",
    "EvidenceProof",
    "EvidenceProvenancePack",
    "ExportTarget",
    "ImportCollisionPolicy",
    "PortabilityAdaptation",
    "PortabilityAmbiguousTargetError",
    "PortabilityBundleExistsError",
    "PortabilityBundleParseError",
    "PortabilityCompatibility",
    "PortabilityContextBudget",
    "PortabilityError",
    "PortabilityImportExistsError",
    "PortabilityImportNotFoundError",
    "PortabilityManifest",
    "PortabilityReadiness",
    "PortabilitySource",
    "PortabilityTarget",
    "PortabilityValidation",
    "ProvenanceIntegrity",
    "RemapBinding",
    "TargetOverlay",
    "TargetOverrides",
    "TargetRunPlan",
    "TargetValidationReport",
    "ToolCompatibilityStatus",
    "ValidationStatus",
    "adapt_capability_package",
    "export_capability_package",
    "import_capability_package",
    "remap_capability_package",
    "validate_capability_package",
]
