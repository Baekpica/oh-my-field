from pathlib import Path
from typing import Literal

from pydantic import Field, model_validator

from oh_my_field.domain.layout import DEFAULT_EVIDENCE_DIR
from oh_my_field.domain.models import (
    CAPABILITY_NAME_PATTERN,
    CommandRiskCategory,
    StrictModel,
)

type ExportTarget = Literal[
    "codex", "claude_code", "hermes", "pi", "odysseus", "generic"
]
type ValidationStatus = Literal["needs_validation", "needs_adaptation", "validated"]
type ToolCompatibilityStatus = Literal["pass", "partial", "unknown"]
type EvidenceInclusionMode = Literal["none", "summary", "redacted", "full"]
type ImportCollisionPolicy = Literal["fail", "merge", "version", "overwrite"]
type ExportBundleFormat = Literal["archive", "dir"]
type SkillStyle = Literal["launcher", "full"]

PORTABILITY_SCHEMA_VERSION = "omf.portability.v0.1"
TARGET_VALIDATION_SCHEMA_VERSION = "omf.target_validation.v0.2"
TARGET_OVERLAY_SCHEMA_VERSION = "omf.target_overlay.v0.2"
RUNTIME_SKILL_SCHEMA_VERSION = "omf.runtime_skill.v0.1"
type ModelClass = Literal["frontier", "standard", "local"]
type CapabilityTier = Literal["high", "medium", "low"]
type RiskLevel = Literal["low", "medium", "high", "severe"]
type ConfidenceLevel = Literal["low", "medium", "high"]
type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)

PORTABILITY_REQUIRED_PASS_RATE = 0.8
REDACTED_MARKER = "[REDACTED]"


class PortabilitySource(StrictModel):
    runtime: str = Field(min_length=1)
    model: str | None = None
    reasoning_effort: str | None = None
    project: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


class PortabilityTarget(StrictModel):
    runtime: ExportTarget
    model: str | None = None
    project: str | None = None


class PortabilityContextBudget(StrictModel):
    source_tokens: int | None = Field(default=None, ge=1)
    target_tokens: int | None = Field(default=None, ge=1)


class PortabilityCompatibility(StrictModel):
    required_tools: tuple[str, ...] = ()
    optional_tools: tuple[str, ...] = ()
    unavailable_tools: tuple[str, ...] = ()
    context_budget: PortabilityContextBudget | None = None
    compression_required: bool = False


class ModelProfile(StrictModel):
    model_class: ModelClass = "standard"
    context_tokens: int | None = Field(default=None, ge=1)
    tool_use: CapabilityTier = "medium"
    reasoning: CapabilityTier = "medium"


DEFAULT_MODEL_PROFILES: dict[str, ModelProfile] = {
    "gpt-5.5": ModelProfile(
        model_class="frontier",
        context_tokens=256000,
        tool_use="high",
        reasoning="high",
    ),
    "qwen3.6-27b": ModelProfile(
        model_class="local",
        context_tokens=32768,
        tool_use="medium",
        reasoning="medium",
    ),
}


class PortabilityModelDelta(StrictModel):
    source_model: str | None = None
    target_model: str | None = None
    model_changed: bool = False
    transfer_type: tuple[str, ...] = ()
    source_profile: ModelProfile | None = None
    target_profile: ModelProfile | None = None
    downgrade: bool = False


class PortabilityAdaptation(StrictModel):
    transfer_type: tuple[str, ...] = ()
    prompt_variant: str = "base"
    context_variant: str = "full"
    harness_required: bool = True
    human_review_required: bool = True


class PortabilityValidation(StrictModel):
    eval_set: str | None = None
    required_pass_rate: float = Field(
        default=PORTABILITY_REQUIRED_PASS_RATE,
        ge=0.0,
        le=1.0,
    )
    current_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ValidationStatus = "needs_validation"


class AgentView(StrictModel):
    """How the target agent is allowed to see this capability.

    A launcher view installs only an OMF entrypoint; the capability body stays
    in the OMF package, so the agent cannot bypass the OMF lifecycle from the
    skill surface alone.
    """

    skill_style: SkillStyle = "launcher"
    direct_execution_allowed: bool = False


class PortabilityManifest(StrictModel):
    schema_version: str = PORTABILITY_SCHEMA_VERSION
    capability: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    lifecycle_owner: Literal["omf"] = "omf"
    source: PortabilitySource
    target: PortabilityTarget
    agent_view: AgentView = Field(default_factory=AgentView)
    compatibility: PortabilityCompatibility = Field(
        default_factory=PortabilityCompatibility,
    )
    adaptation: PortabilityAdaptation = Field(default_factory=PortabilityAdaptation)
    validation: PortabilityValidation = Field(default_factory=PortabilityValidation)


class EvidenceProof(StrictModel):
    evidence_id: str = Field(min_length=1)
    available: bool
    sha256: str | None = None
    integrity_verified: bool = False
    summary_path: str | None = None
    snapshot_path: str | None = None


class EvidenceProvenancePack(StrictModel):
    mode: EvidenceInclusionMode
    proofs: tuple[EvidenceProof, ...] = ()


class EvidenceIntegrityProof(StrictModel):
    evidence_id: str = Field(min_length=1)
    available: bool
    sha256: str | None = None
    integrity_verified: bool = False


class ProvenanceIntegrity(StrictModel):
    capability: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capability_sha256: str | None = None
    capability_integrity_verified: bool = False
    evidence: tuple[EvidenceIntegrityProof, ...] = ()


class ReadinessFactor(StrictModel):
    name: str = Field(min_length=1)
    delta: float
    reason: str = Field(min_length=1)


class PortabilityReadiness(StrictModel):
    score: float = Field(ge=0.0, le=1.0)
    required_pass_rate: float = Field(ge=0.0, le=1.0)
    factors: tuple[ReadinessFactor, ...] = ()


class ValidationIssue(StrictModel):
    name: str = Field(min_length=1)
    message: str = Field(min_length=1)
    action: str | None = None
    path: str | None = None


class PortabilityRisk(StrictModel):
    score: float = Field(ge=0.0, le=1.0)
    level: RiskLevel
    advisory_only: bool = True
    factors: tuple[ReadinessFactor, ...] = ()


class ValidationConfidenceFactor(StrictModel):
    name: str = Field(min_length=1)
    observed: bool
    message: str = Field(min_length=1)


class ValidationConfidence(StrictModel):
    score: float = Field(ge=0.0, le=1.0)
    level: ConfidenceLevel
    advisory_only: bool = True
    factors: tuple[ValidationConfidenceFactor, ...] = ()


class EvalPassRateComparison(StrictModel):
    source_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    target_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    delta: float | None = None


class TargetRunPlan(StrictModel):
    target_run_command: str | None = None
    manual_run_required: bool = True
    manual_run_reason: str | None = None
    expected_artifacts: tuple[str, ...] = ()
    executed: bool = False
    approved: bool = False
    exit_code: int | None = None
    risk_categories: tuple[CommandRiskCategory, ...] = ()


class TargetValidationReport(StrictModel):
    schema_version: str = TARGET_VALIDATION_SCHEMA_VERSION
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source: PortabilitySource
    target: PortabilityTarget
    tool_compatibility: ToolCompatibilityStatus
    unavailable_tools: tuple[str, ...] = ()
    context_remap_required: bool = False
    eval_set: str | None = None
    initial_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    readiness: PortabilityReadiness
    hard_blockers: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    portability_risk: PortabilityRisk
    validation_confidence: ValidationConfidence
    model_delta: PortabilityModelDelta
    target_run: TargetRunPlan | None = None
    pass_rate_comparison: EvalPassRateComparison | None = None
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None
    compact_instruction_path: str | None = None
    compressed_context_path: str | None = None
    status: ValidationStatus
    next_action: str = Field(min_length=1)


class TargetOverrides(StrictModel):
    instruction_variant: str = "base"
    context_variant: str = "full"
    required_human_review: bool = True


class TargetOverlay(StrictModel):
    schema_version: str = TARGET_OVERLAY_SCHEMA_VERSION
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source: PortabilitySource
    target: PortabilityTarget
    direct_execution_allowed: bool = False
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_readiness_score: float = Field(ge=0.0, le=1.0)
    hard_blockers: tuple[ValidationIssue, ...] = ()
    warnings: tuple[ValidationIssue, ...] = ()
    portability_risk: PortabilityRisk | None = None
    transfer_type: tuple[str, ...] = ()
    overrides: TargetOverrides = Field(default_factory=TargetOverrides)
    validation_report_path: str = "validation_report.yaml"
    instructions_path: str = "instructions.md"
    context_pack_path: str = "context.pack.md"
    eval_id: str | None = None
    failure_evidence_id: str | None = None


class CapabilityPortabilityExportRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    out: Path
    capabilities_dir: Path
    target_model: str | None = None
    target_project: str | None = None
    source_project: str | None = None
    source_reasoning_effort: str | None = None
    source_context_tokens: int | None = Field(default=None, ge=1)
    target_context_tokens: int | None = Field(default=None, ge=1)
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR
    include_evidence: EvidenceInclusionMode = "summary"
    skill_style: SkillStyle = "launcher"
    bundle_format: ExportBundleFormat = "archive"


class CapabilityPortabilityExportSummary(StrictModel):
    capability_name: str
    export_path: str
    package_path: str
    unpacked_path: str | None = None
    portability_path: str
    runtime_export_path: str
    target_runtime: ExportTarget
    target_model: str | None = None
    bundle_format: ExportBundleFormat = "archive"
    evidence_mode: EvidenceInclusionMode = "summary"
    evidence_proof_count: int = Field(default=0, ge=0)
    next_action: str = Field(min_length=1)


class CapabilityExportRecord(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: PortabilityTarget
    transfer_type: tuple[str, ...] = ()
    bundle_path: str = Field(min_length=1)
    evidence_mode: EvidenceInclusionMode = "summary"
    evidence_proof_count: int = Field(default=0, ge=0)


class CapabilityPortabilityImportRequest(StrictModel):
    bundle_path: Path
    import_dir: Path = Path(".omf/imports")
    capabilities_dir: Path
    eval_dir: Path
    evidence_dir: Path
    runtime: ExportTarget | None = None
    model: str | None = None
    project: str | None = None
    validate_import: bool = False
    available_tools: tuple[str, ...] = ()
    as_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    namespace: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    if_exists: ImportCollisionPolicy = "fail"


class CapabilityPortabilityImportSummary(StrictModel):
    capability_name: str
    package_path: str
    unpacked_path: str | None = None
    imported_package_path: str
    validation_report_path: str
    overlay_path: str
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_readiness_score: float = Field(ge=0.0, le=1.0)
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None
    next_commands: tuple[str, ...] = ()


class CapabilityValidationRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    eval_dir: Path
    evidence_dir: Path
    target: ExportTarget
    model: str | None = None
    project: str | None = None
    available_tools: tuple[str, ...] = ()
    run_command: str | None = None
    run_argv: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    command_cwd: Path = Path()
    command_timeout_seconds: int = Field(default=600, ge=1)
    approve_command_risk: bool = False
    run_contract_validator: bool = False
    require_cwd_inside_project: bool = False
    allow_env: tuple[str, ...] = ()

    @model_validator(mode="after")
    def _reject_dual_command_forms(self) -> "CapabilityValidationRequest":
        if self.run_argv and self.run_command is not None:
            message = "run_command and run_argv are mutually exclusive"
            raise ValueError(message)
        return self


class CapabilityValidationSummary(StrictModel):
    capability_name: str
    package_path: str | None = None
    unpacked_path: str | None = None
    imported_package_path: str
    overlay_path: str
    validation_report_path: str
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_readiness_score: float = Field(ge=0.0, le=1.0)
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None
    target_run_executed: bool = False
    target_run_exit_code: int | None = None
    manual_run_required: bool = True
    manual_run_reason: str | None = None
    next_commands: tuple[str, ...] = ()


class RemapBinding(StrictModel):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class ContextRemapPlan(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: PortabilityTarget
    bindings: tuple[RemapBinding, ...] = ()
    unresolved: tuple[str, ...] = ()


class CapabilityRemapRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    target: ExportTarget
    model: str | None = None
    target_project: str | None = None
    mappings: tuple[tuple[str, str], ...] = ()
    unresolved: tuple[str, ...] = ()


class CapabilityRemapSummary(StrictModel):
    capability_name: str
    remap_path: str
    binding_count: int = Field(ge=0)
    unresolved: tuple[str, ...] = ()
    complete: bool
    next_action: str = Field(min_length=1)


class CapabilityAdaptRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    target: ExportTarget
    model: str | None = None
    instruction_variant: Literal["base", "compact"] | None = None
    context_variant: Literal["full", "compressed"] | None = None
    require_human_review: bool | None = None


class CapabilityAdaptSummary(StrictModel):
    capability_name: str
    overlay_path: str
    instruction_variant: str
    context_variant: str
    required_human_review: bool
    next_action: str = Field(min_length=1)
