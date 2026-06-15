from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_EVIDENCE_DIR,
    DEFAULT_LEARNING_PATCH_DIR,
    DEFAULT_MCP_CONFIG_PATH,
    DEFAULT_SESSIONS_DIR,
)
from oh_my_field.domain.models import (
    CAPABILITY_NAME_PATTERN,
    EVIDENCE_ID_PATTERN,
    CommandRiskCategory,
    StrictModel,
    TaskOutcome,
)
from oh_my_field.domain.portability.models import (
    EvidenceInclusionMode,
    ExportBundleFormat,
    ExportTarget,
    ImportCollisionPolicy,
    SkillStyle,
)
from oh_my_field.domain.session.models import AgentSessionEventType


class StartSessionToolRequest(StrictModel):
    runtime: str = Field(min_length=1)
    model: str | None = None
    project_root: Path = Path()
    goal: str = Field(min_length=1)
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class RecordEventToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    type: AgentSessionEventType
    summary: str = Field(min_length=1)
    artifact_path: str | None = None
    command: str | None = None
    exit_code: int | None = None
    risk_categories: tuple[CommandRiskCategory, ...] = ()
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class RecordInputToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    path: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class RecordArtifactToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    path: str = Field(min_length=1)
    summary: str = Field(min_length=1)
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class RecordValidationToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    summary: str = Field(min_length=1)
    artifact_path: str | None = None
    command: str | None = None
    exit_code: int | None = 0
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class RecordDecisionToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    summary: str = Field(min_length=1)
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class FinishSessionToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    outcome: TaskOutcome
    sessions_dir: Path = DEFAULT_SESSIONS_DIR


class MaterializeSessionToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    sessions_dir: Path = DEFAULT_SESSIONS_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR


class PromoteCapabilityToolRequest(StrictModel):
    evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0", min_length=1)
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    strict: bool = True


class ExportCapabilityToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    out: Path
    target_model: str | None = None
    target_project: str | None = None
    source_project: str | None = None
    source_reasoning_effort: str | None = None
    source_context_tokens: int | None = Field(default=None, ge=1)
    target_context_tokens: int | None = Field(default=None, ge=1)
    include_evidence: EvidenceInclusionMode = "summary"
    skill_style: SkillStyle = "launcher"
    bundle_format: ExportBundleFormat = "archive"
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR


class HealthToolRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR


class ListCapabilitiesToolRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR


class InspectCapabilityToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class CapabilityInspectToolSummary(StrictModel):
    capability_name: str
    version: str
    description: str
    status: str
    normalized_goal: str
    runtime_name: str
    runtime_model: str | None = None
    runtime_tools: tuple[str, ...] = ()
    required_context: tuple[str, ...] = ()
    forbidden_context: tuple[str, ...] = ()
    required_checks: tuple[str, ...] = ()
    source_evidence_ids: tuple[str, ...] = ()


class ValidateCapabilityToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    model: str | None = None
    project: str | None = None
    available_tools: tuple[str, ...] = ()
    run_command: str | None = None
    run_argv: tuple[str, ...] = ()
    expected_artifacts: tuple[str, ...] = ()
    command_cwd: Path = Path()
    command_timeout_seconds: int = Field(default=600, ge=1)
    run_contract_validator: bool = False
    require_cwd_inside_project: bool = False
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR
    # NOTE: approve_command_risk and allow_env are intentionally NOT exposed over
    # MCP. MCP tool arguments are chosen by the connected agent/client, so letting
    # them self-approve risky commands or opt secret env vars back in would bypass
    # the record-don't-execute boundary. Risky run commands over MCP are recorded
    # as intent (manual_run_required) and require out-of-band CLI approval.


class ImportCapabilityToolRequest(StrictModel):
    bundle_path: Path
    runtime: ExportTarget | None = None
    model: str | None = None
    project: str | None = None
    validate_import: bool = False
    available_tools: tuple[str, ...] = ()
    as_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    namespace: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    if_exists: ImportCollisionPolicy = "fail"
    import_dir: Path = Path(".omf/imports")
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR


class RemapCapabilityToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    model: str | None = None
    target_project: str | None = None
    mappings: dict[str, str] = Field(default_factory=dict)
    unresolved: tuple[str, ...] = ()
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class AdaptCapabilityToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    model: str | None = None
    instruction_variant: Literal["base", "compact"] | None = None
    context_variant: Literal["full", "compressed"] | None = None
    require_human_review: bool | None = None
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR


class ExplainToolRequest(StrictModel):
    target_type: Literal["capability", "harness", "learning-patch"]
    target_id: str = Field(min_length=1)
    rule: str | None = None
    check: str | None = None
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    learning_patch_dir: Path = DEFAULT_LEARNING_PATCH_DIR


class CardToolRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    write: bool = False


class McpToolDefinition(StrictModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, object]


type McpInstallClient = Literal[
    "generic", "codex", "claude_code", "hermes", "pi", "odysseus"
]
type McpInstallScope = Literal["auto", "user", "project", "export"]
type ResolvedMcpInstallScope = Literal["user", "project", "export"]


class McpInstallRequest(StrictModel):
    client: McpInstallClient
    project: Path = Path()
    out: Path = DEFAULT_MCP_CONFIG_PATH
    scope: McpInstallScope = "auto"
    home: Path | None = None
    server_command: str | None = Field(default=None, min_length=1)
    dry_run: bool = False
    overwrite: bool = False


class McpInstallAction(StrictModel):
    target_path: str
    action: Literal["write", "skip_existing", "plan_only"]
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class McpInstallSummary(StrictModel):
    client: McpInstallClient
    scope: ResolvedMcpInstallScope
    installed: bool
    dry_run: bool = False
    server_name: str = "oh-my-field"
    config_path: str
    backup_path: str | None = None
    actions: tuple[McpInstallAction, ...] = ()
    next_action: str = Field(min_length=1)
