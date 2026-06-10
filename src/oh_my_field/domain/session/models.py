from datetime import datetime
from typing import Literal

from pydantic import Field

from oh_my_field.domain.models import (
    EVIDENCE_ID_PATTERN,
    CommandRiskCategory,
    StrictModel,
    TaskOutcome,
)

type SessionActivationSource = Literal["skill", "mcp", "cli", "manual"]
type AgentSessionStatus = Literal["active", "completed", "failed", "abandoned"]
type AgentSessionEventType = Literal[
    "goal",
    "assumption",
    "context",
    "command",
    "diff",
    "test_result",
    "artifact",
    "user_feedback",
    "decision",
    "completion",
]


class AgentSessionEvent(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    type: AgentSessionEventType
    summary: str = Field(min_length=1)
    path: str | None = None
    command: str | None = None
    exit_code: int | None = None
    risk_categories: tuple[CommandRiskCategory, ...] = ()


class AgentSession(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    updated_at: datetime
    runtime: str = Field(min_length=1)
    model: str | None = None
    project_root: str = Field(min_length=1)
    activation_source: SessionActivationSource
    goal: str = Field(min_length=1)
    status: AgentSessionStatus = "active"
    outcome: TaskOutcome = "unknown"
    events: tuple[AgentSessionEvent, ...] = ()
    evidence_ids: tuple[str, ...] = ()
    suggested_capabilities: tuple[str, ...] = ()


class SessionStartSummary(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    session_path: str
    status: AgentSessionStatus
    next_action: str


class SessionEventSummary(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    event_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    event_count: int = Field(ge=1)
    session_path: str
    next_action: str = "record input, artifact, validation, and decision events"


class SessionFinishSummary(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    status: AgentSessionStatus
    outcome: TaskOutcome
    session_path: str
    next_action: str


class SessionMaterializeSummary(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    evidence_path: str
    session_path: str
    next_action: str


class SessionSuggestSummary(StrictModel):
    session_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    suggested_capabilities: tuple[str, ...] = Field(
        default=(),
        min_length=1,
    )
    session_path: str
