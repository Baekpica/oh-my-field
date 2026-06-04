from pathlib import Path
from typing import Literal

from pydantic import Field

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
    sessions_dir: Path = Path(".omf/sessions")


class RecordEventToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    type: AgentSessionEventType
    summary: str = Field(min_length=1)
    artifact_path: str | None = None
    command: str | None = None
    exit_code: int | None = None
    risk_categories: tuple[CommandRiskCategory, ...] = ()
    sessions_dir: Path = Path(".omf/sessions")


class FinishSessionToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    outcome: TaskOutcome
    sessions_dir: Path = Path(".omf/sessions")


class MaterializeSessionToolRequest(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    sessions_dir: Path = Path(".omf/sessions")
    evidence_dir: Path = Path(".omf/evidence")


class PromoteCapabilityToolRequest(StrictModel):
    evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0", min_length=1)
    evidence_dir: Path = Path(".omf/evidence")
    eval_dir: Path = Path(".omf/evals")
    capabilities_dir: Path = Path("capabilities")


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
    capabilities_dir: Path = Path("capabilities")
    evidence_dir: Path = Path(".omf/evidence")


class HealthToolRequest(StrictModel):
    capability_name: str | None = Field(default=None, pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path = Path("capabilities")
    eval_dir: Path = Path(".omf/evals")


class McpToolDefinition(StrictModel):
    name: str = Field(min_length=1)
    description: str = Field(min_length=1)
    input_schema: dict[str, object]


type McpInstallClient = Literal["generic"]


class McpInstallRequest(StrictModel):
    client: McpInstallClient
    project: Path = Path()
    out: Path = Path(".omf/mcp.json")
    dry_run: bool = False
    overwrite: bool = False


class McpInstallAction(StrictModel):
    target_path: str
    action: Literal["write", "skip_existing", "plan_only"]
    source: str = Field(min_length=1)
    reason: str = Field(min_length=1)


class McpInstallSummary(StrictModel):
    client: McpInstallClient
    installed: bool
    dry_run: bool = False
    server_name: str = "oh-my-field"
    config_path: str
    actions: tuple[McpInstallAction, ...] = ()
    next_action: str = Field(min_length=1)
