from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field

EVIDENCE_ID_PATTERN: Final = r"^[0-9]{8}T[0-9]{6}Z-[a-f0-9]{8}$"
CAPABILITY_NAME_PATTERN: Final = r"^[a-z][a-z0-9_]*$"
SHA256_PATTERN: Final = r"^[a-f0-9]{64}$"

type CapturedFileRole = Literal[
    "prompt",
    "context",
    "tool_call",
    "command_output",
    "diff",
    "test_result",
    "artifact",
]
type HarnessStatus = Literal["pass", "fail"]
type EvalStatus = Literal["pass", "fail"]
type CapabilityStatus = Literal["candidate", "validated", "stable", "deprecated"]
type WorkflowGraph = Literal["langgraph"]
type SuccessLabel = Literal["success", "failure", "unknown"]
type AgentImporterName = Literal["codex", "claude_code", "hermes"]
type RuntimeAdapterName = AgentImporterName
type ContextSourceType = Literal[
    "repo",
    "docs",
    "logs",
    "evidence",
    "review",
    "preference",
]
type CommandRiskCategory = Literal[
    "write",
    "destructive",
    "external_call",
    "credential_access",
    "production_write",
    "paid_operation",
]
type NetworkPolicy = Literal["disabled", "internal_only", "allowed"]
type ReviewTargetType = Literal["evidence", "capability", "replay", "eval"]
type HumanReviewAction = Literal[
    "approve",
    "reject",
    "revise",
    "add_context",
    "change_goal",
    "change_constraint",
    "mark_reusable",
    "mark_unsafe",
    "create_regression_case",
]
type HumanReviewStatus = Literal[
    "pending",
    "approved",
    "rejected",
    "revision_requested",
    "context_added",
    "goal_changed",
    "constraint_changed",
    "marked_reusable",
    "marked_unsafe",
    "regression_case_created",
]
type WorkflowRunStatus = Literal["running", "completed", "failed", "pending_review"]
type WorkflowNodeStatus = Literal["pending", "pass", "fail", "skipped"]
type PatchDecisionStatus = Literal["accepted", "rejected"]
type PatchKind = Literal["prompt", "context", "harness"]
type IntegrityVerificationStatus = Literal["pass", "fail"]
type ArtifactStorageMode = Literal["inline", "external"]
type ExportStatus = Literal["not_exported", "exported"]
type ImportStatus = Literal["not_imported", "imported"]
type TargetValidationStatus = Literal[
    "not_run",
    "needs_validation",
    "needs_adaptation",
    "validated",
]

COMMAND_RISK_CATEGORIES: Final[tuple[CommandRiskCategory, ...]] = (
    "write",
    "destructive",
    "external_call",
    "credential_access",
    "production_write",
    "paid_operation",
)


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeInfo(StrictModel):
    name: str = Field(min_length=1)
    model: str | None = None
    preferred_models: tuple[str, ...] = ()
    tools: tuple[str, ...] = ()


class RuntimeRunSource(StrictModel):
    adapter: RuntimeAdapterName
    path: str = Field(min_length=1)


class AgentRunSource(StrictModel):
    importer: AgentImporterName
    path: str = Field(min_length=1)


class AgentImporterSpec(StrictModel):
    name: AgentImporterName
    display_name: str = Field(min_length=1)
    captures: tuple[str, ...] = ()
    replays: tuple[str, ...] = ()
    artifact_roles: tuple[CapturedFileRole, ...] = ()


class RuntimeAdapterSpec(AgentImporterSpec):
    pass


class ToolCallRecord(StrictModel):
    tool: str = Field(min_length=1)
    input: str = ""
    output: str = ""


class CommandExecution(StrictModel):
    command: str = Field(min_length=1)
    cwd: str = Field(min_length=1)
    exit_code: int
    stdout: str = ""
    stderr: str = ""
    duration_ms: int = Field(ge=0)
    risk_categories: tuple[CommandRiskCategory, ...] = ()
    approval_required: bool = False
    approved: bool = False


class CostMetrics(StrictModel):
    input_tokens: int = Field(default=0, ge=0)
    output_tokens: int = Field(default=0, ge=0)
    total_cost_usd: float = Field(default=0.0, ge=0.0)


class LatencyMetrics(StrictModel):
    total_ms: int = Field(default=0, ge=0)
    tool_ms: int = Field(default=0, ge=0)


class ContextSource(StrictModel):
    name: str = Field(min_length=1)
    type: ContextSourceType
    location: str = Field(min_length=1)
    freshness: str | None = None
    priority: int = Field(default=100, ge=0)


class FieldPreference(StrictModel):
    key: str = Field(min_length=1)
    value: str = Field(min_length=1)


class FieldPolicy(StrictModel):
    network: NetworkPolicy = "disabled"
    require_approval: tuple[CommandRiskCategory, ...] = COMMAND_RISK_CATEGORIES
    forbidden_context: tuple[str, ...] = ()


class FieldQualityBar(StrictModel):
    required_checks: tuple[str, ...] = ()
    human_review_required: bool = True


class FieldFailureHistory(StrictModel):
    recall_strategy: str | None = None
    cases: tuple[str, ...] = ()


class FieldManifest(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    description: str = Field(min_length=1)
    sources: tuple[ContextSource, ...] = ()
    policies: FieldPolicy = Field(default_factory=FieldPolicy)
    quality_bar: FieldQualityBar = Field(default_factory=FieldQualityBar)
    preferences: tuple[FieldPreference, ...] = ()
    failure_history: FieldFailureHistory = Field(default_factory=FieldFailureHistory)


class ContextItem(StrictModel):
    path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    token_estimate: int = Field(ge=0)
    source_type: ContextSourceType | None = None
    freshness: str | None = None
    priority: int = Field(default=100, ge=0)
    matched_query: bool = False
    compressed: bool = False


class ExcludedContextItem(StrictModel):
    path: str = Field(min_length=1)
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)
    source_type: ContextSourceType | None = None
    freshness: str | None = None
    priority: int = Field(default=100, ge=0)


class ContextPackPlan(StrictModel):
    required: tuple[ContextItem, ...] = ()
    optional: tuple[ContextItem, ...] = ()
    excluded: tuple[ExcludedContextItem, ...] = ()
    token_estimate: int = Field(ge=0)
    compression_strategy: str = Field(min_length=1)
    source_priority: tuple[str, ...] = ()
    recall_notes: tuple[str, ...] = ()


class ArtifactIntegrityLink(StrictModel):
    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    sha256: str = Field(pattern=SHA256_PATTERN)
    previous_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class IntegrityVerificationCheck(StrictModel):
    artifact_type: str = Field(min_length=1)
    artifact_id: str = Field(min_length=1)
    status: IntegrityVerificationStatus
    message: str = Field(min_length=1)
    expected_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)
    actual_sha256: str | None = Field(default=None, pattern=SHA256_PATTERN)


class IntegrityVerificationResult(StrictModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    status: IntegrityVerificationStatus
    checks: tuple[IntegrityVerificationCheck, ...]


class TargetStatusEntry(StrictModel):
    target: str = Field(min_length=1)
    validation_status: TargetValidationStatus
    portability_readiness_score: float | None = Field(default=None, ge=0.0, le=1.0)
    eval_recorded: bool = False


class PortabilityHealth(StrictModel):
    export_status: ExportStatus = "not_exported"
    import_status: ImportStatus = "not_imported"
    validation_status: TargetValidationStatus = "not_run"
    export_count: int = Field(default=0, ge=0)
    import_count: int = Field(default=0, ge=0)
    target_validation_count: int = Field(default=0, ge=0)
    target_statuses: tuple[TargetStatusEntry, ...] = ()


class HumanReview(StrictModel):
    status: HumanReviewStatus = "pending"
    reviewer: str | None = None
    notes: tuple[str, ...] = ()
    revision_request: str | None = None
    added_context: tuple[str, ...] = ()
    changed_goal: str | None = None
    changed_constraint: str | None = None
    reusable: bool | None = None
    unsafe: bool | None = None
    regression_case: str | None = None
    reviewed_at: datetime | None = None


class CapturedTextFile(StrictModel):
    role: CapturedFileRole
    path: str = Field(min_length=1)
    content: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=SHA256_PATTERN)
    mime_type: str | None = None
    storage_mode: ArtifactStorageMode = "inline"
    redacted: bool = False


class HarnessResult(StrictModel):
    status: HarnessStatus
    checks: tuple[str, ...]
    failures: tuple[str, ...] = ()
    required_checks: tuple[str, ...] = ()
    human_review_required: bool = False


class EvidenceRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    session_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    capability_id: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    created_at: datetime
    goal: str = Field(min_length=1)
    normalized_goal: str | None = None
    field: str = Field(min_length=1)
    runtime: RuntimeInfo
    input_context: tuple[str, ...] = ()
    files: tuple[CapturedTextFile, ...] = ()
    tool_calls: tuple[ToolCallRecord, ...] = ()
    generated_commands: tuple[str, ...] = ()
    generated_scripts: tuple[str, ...] = ()
    command_executions: tuple[CommandExecution, ...] = ()
    execution_outputs: tuple[str, ...] = ()
    errors: tuple[str, ...] = ()
    retries: int = Field(default=0, ge=0)
    feedback: tuple[str, ...] = ()
    user_interventions: tuple[str, ...] = ()
    final_artifacts: tuple[str, ...] = ()
    harness: HarnessResult
    cost_metrics: CostMetrics = Field(default_factory=CostMetrics)
    latency_metrics: LatencyMetrics = Field(default_factory=LatencyMetrics)
    success_or_failure_label: SuccessLabel = "unknown"
    improvement_notes: tuple[str, ...] = ()
    human_review: HumanReview = Field(default_factory=HumanReview)
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class WorkflowManifest(StrictModel):
    graph: WorkflowGraph
    nodes: tuple[str, ...] = Field(min_length=1)


class ContextPolicy(StrictModel):
    required: tuple[str, ...] = ()
    optional: tuple[str, ...] = ()
    forbidden: tuple[str, ...] = ()
    sources: tuple[ContextSource, ...] = ()
    retrieval_query_template: str | None = None
    summarization_rule: str | None = None
    compression_rule: str | None = None
    freshness_rule: str | None = None
    source_priority: tuple[str, ...] = ()
    maximum_token_budget: int | None = Field(default=None, ge=1)
    evidence_recall_strategy: str | None = None


class EvidencePolicy(StrictModel):
    store: tuple[str, ...] = ()


class WorkflowControl(StrictModel):
    max_iterations: int | None = Field(default=None, ge=1)
    max_runtime_seconds: int | None = Field(default=None, ge=1)
    max_cost_usd: float | None = Field(default=None, ge=0.0)
    allowed_tools: tuple[str, ...] = ()
    disallowed_tools: tuple[str, ...] = ()
    require_approval_before_write: bool = True
    require_approval_before_external_call: bool = True
    require_approval_before_destructive_action: bool = True
    approval_required_actions: tuple[CommandRiskCategory, ...] = COMMAND_RISK_CATEGORIES
    safe_execution_mode: bool = True
    credential_scope: str | None = None
    network_policy: NetworkPolicy = "disabled"
    rollback_policy: str | None = None
    checkpoint_interval: int | None = Field(default=None, ge=1)
    rollback_strategy: str | None = None
    resume_from_checkpoint: str | None = None


class PromotionCriteria(StrictModel):
    min_success_runs: int = Field(ge=1)
    max_human_intervention_rate: float = Field(ge=0.0, le=1.0)
    required_harness_pass_rate: float = Field(ge=0.0, le=1.0)
    min_runtime_profiles: tuple[str, ...] = ()


class PromotionMetrics(StrictModel):
    evidence_count: int = Field(ge=0)
    successful_evidence_count: int = Field(ge=0)
    failed_evidence_count: int = Field(ge=0)
    harness_pass_rate: float = Field(ge=0.0, le=1.0)
    human_intervention_rate: float = Field(ge=0.0, le=1.0)
    retry_rate: float = Field(ge=0.0)
    eval_count: int = Field(default=0, ge=0)
    eval_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    runtime_profiles: tuple[str, ...] = ()
    criteria_met: bool = False
    eval_gate_met: bool = True
    recommended_version_bump: str = "patch"


class CapabilityPatchSet(StrictModel):
    prompt: tuple[str, ...] = ()
    context: tuple[str, ...] = ()
    harness: tuple[str, ...] = ()


class CapabilityManifest(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: CapabilityStatus
    owner: str | None = None
    dependencies: tuple[str, ...] = ()
    runtime_compatibility: tuple[str, ...] = ()
    evaluation_results: tuple[str, ...] = ()
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    source_evidence_ids: tuple[str, ...] = ()
    field: FieldManifest | None = None
    normalized_goal: str = Field(min_length=1)
    inputs: tuple[str, ...]
    context: ContextPolicy = Field(default_factory=ContextPolicy)
    workflow: WorkflowManifest
    harness: HarnessResult
    runtime: RuntimeInfo
    evidence: EvidencePolicy = Field(default_factory=EvidencePolicy)
    workflow_control: WorkflowControl = Field(default_factory=WorkflowControl)
    human_review: HumanReview = Field(default_factory=HumanReview)
    promotion_criteria: PromotionCriteria
    promotion_metrics: PromotionMetrics | None = None
    patches: CapabilityPatchSet = Field(default_factory=CapabilityPatchSet)
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class ReplayRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    source_goal: str = Field(min_length=1)
    workflow: WorkflowManifest
    harness: HarnessResult
    runtime: RuntimeInfo
    runtime_profile: str | None = None
    command_executions: tuple[CommandExecution, ...] = ()
    human_review: HumanReview = Field(default_factory=HumanReview)
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class EvalCheck(StrictModel):
    name: str = Field(min_length=1)
    status: EvalStatus
    message: str = Field(min_length=1)


class EvalChecklistItem(StrictModel):
    name: str = Field(min_length=1)
    status: EvalStatus
    message: str = Field(min_length=1)


class EvalRubricScore(StrictModel):
    name: str = Field(min_length=1)
    score: float = Field(ge=0.0)
    max_score: float = Field(gt=0.0)
    pass_threshold: float = Field(ge=0.0)
    status: EvalStatus
    message: str = Field(min_length=1)


class EvalCaseInput(StrictModel):
    name: str = Field(min_length=1)
    value: str = Field(min_length=1)


class EvalExpectedCheck(StrictModel):
    name: str = Field(min_length=1)
    flaky: bool = False


class EvalCase(StrictModel):
    id: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    input: tuple[EvalCaseInput, ...] = ()
    expected_checks: tuple[EvalExpectedCheck, ...] = ()
    harness_commands: tuple[str, ...] = ()


class EvalSet(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    cases: tuple[EvalCase, ...] = ()


class EvalResult(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    replay_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    runtime_profile: str | None = None
    eval_set_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    eval_case_ids: tuple[str, ...] = ()
    status: EvalStatus
    checks: tuple[EvalCheck, ...]
    failures: tuple[str, ...] = ()
    command_executions: tuple[CommandExecution, ...] = ()
    checklist_items: tuple[EvalChecklistItem, ...] = ()
    rubric_scores: tuple[EvalRubricScore, ...] = ()
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class HumanReviewRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    target_type: ReviewTargetType
    target_id: str = Field(min_length=1)
    action: HumanReviewAction
    review: HumanReview
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class LearningExport(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    prompt_improvement_candidates: tuple[str, ...] = ()
    regression_eval_candidates: tuple[str, ...] = ()
    few_shot_examples: tuple[str, ...] = ()
    preference_signals: tuple[str, ...] = ()
    prompt_patches: tuple[str, ...] = ()
    context_patches: tuple[str, ...] = ()
    harness_patches: tuple[str, ...] = ()
    eval_set_candidates: tuple[str, ...] = ()
    fine_tuning_candidates: tuple[str, ...] = ()
    fine_tuning_export_format: str = "jsonl"
    preference_dataset_candidates: tuple[str, ...] = ()
    preference_dataset_schema: str = (
        "prompt,accepted_output,rejected_output,source_evidence_id"
    )
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class LearningPatchDecision(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    learning_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    patch_kind: PatchKind = "prompt"
    patch: str = Field(min_length=1)
    decision: PatchDecisionStatus
    reviewer: str | None = None
    notes: tuple[str, ...] = ()
    manifest_path: str | None = None
    before_eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    after_eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    pass_rate_delta: float | None = None
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class ContextBundle(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    required_context: tuple[CapturedTextFile, ...] = ()
    optional_context: tuple[CapturedTextFile, ...] = ()
    summaries: tuple[str, ...] = ()
    compressed_context: tuple[CapturedTextFile, ...] = ()
    policy: ContextPolicy
    pack_plan: ContextPackPlan | None = None
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class WorkflowFileInput(StrictModel):
    role: CapturedFileRole
    path: str = Field(min_length=1)


class WorkflowRunConfig(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    description: str = Field(min_length=1)
    version: str = Field(min_length=1)
    field: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    model: str | None = None
    runtime_tools: tuple[str, ...] = ()
    files: tuple[WorkflowFileInput, ...] = ()
    commands: tuple[str, ...] = ()
    command_cwd: str = Field(min_length=1)
    command_timeout_seconds: int = Field(ge=1)
    approve_command_risk: bool = False
    harness_commands: tuple[str, ...] = ()
    checklist_items: tuple[EvalChecklistItem, ...] = ()
    rubric_scores: tuple[EvalRubricScore, ...] = ()
    execute_replay_commands: bool = True
    include_optional_context: bool = True
    allow_failed_capture: bool = False
    evidence_dir: str = Field(min_length=1)
    capabilities_dir: str = Field(min_length=1)
    replay_dir: str = Field(min_length=1)
    eval_dir: str = Field(min_length=1)
    context_dir: str = Field(min_length=1)
    learning_dir: str = Field(min_length=1)


class WorkflowNodeResult(StrictModel):
    name: str = Field(min_length=1)
    status: WorkflowNodeStatus
    message: str = Field(min_length=1)
    path: str | None = None


class WorkflowRunRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    updated_at: datetime
    goal: str = Field(min_length=1)
    status: WorkflowRunStatus
    current_node: str | None = None
    completed_nodes: tuple[str, ...] = ()
    failed_node: str | None = None
    failure_reason: str | None = None
    config: WorkflowRunConfig
    nodes: tuple[WorkflowNodeResult, ...] = ()
    evidence_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    replay_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    context_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    learning_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)


class CapabilityRegistryEntry(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: CapabilityStatus
    owner: str | None = None
    dependencies: tuple[str, ...] = ()
    runtime_compatibility: tuple[str, ...] = ()
    evaluation_results: tuple[str, ...] = ()
    source_evidence_count: int = Field(default=1, ge=0)
    eval_count: int = Field(default=0, ge=0)
    latest_eval_status: EvalStatus | None = None
    pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    runtime_profiles: tuple[str, ...] = ()
    patch_count: int = Field(default=0, ge=0)
    promotion_success_runs: int = Field(default=0, ge=0)
    promotion_harness_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    promotion_eval_pass_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    promotion_criteria_met: bool = False
    integrity_status: IntegrityVerificationStatus = "fail"
    next_action: str = Field(min_length=1)
    manifest_path: str = Field(min_length=1)


class CapabilityRegistry(StrictModel):
    generated_at: datetime
    entries: tuple[CapabilityRegistryEntry, ...]


class ReflectionReport(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    eval_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    failure_categories: tuple[str, ...] = ()
    retry_strategy: str = Field(min_length=1)
    context_additions: tuple[str, ...] = ()
    prompt_patches: tuple[str, ...] = ()
    tool_call_revisions: tuple[str, ...] = ()
    notes: tuple[str, ...] = ()
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()


class CapabilityExportBundle(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    eval_results: tuple[EvalResult, ...] = ()
    context_bundles: tuple[ContextBundle, ...] = ()
    learning_exports: tuple[LearningExport, ...] = ()
    reflection_reports: tuple[ReflectionReport, ...] = ()
    integrity_chain: tuple[ArtifactIntegrityLink, ...] = ()
