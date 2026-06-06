from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.domain.layout import (
    DEFAULT_CAPABILITIES_DIR,
    DEFAULT_EVAL_DIR,
    DEFAULT_EVIDENCE_DIR,
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
    ExportTarget,
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
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    evidence_dir: Path = DEFAULT_EVIDENCE_DIR


class HealthToolRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = DEFAULT_CAPABILITIES_DIR
    eval_dir: Path = DEFAULT_EVAL_DIR


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
