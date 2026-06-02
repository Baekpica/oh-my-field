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
type CapabilityStatus = Literal["candidate"]
type WorkflowGraph = Literal["langgraph"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class RuntimeInfo(StrictModel):
    name: str = Field(min_length=1)
    model: str | None = None


class CapturedTextFile(StrictModel):
    role: CapturedFileRole
    path: str = Field(min_length=1)
    content: str
    size_bytes: int = Field(ge=0)
    sha256: str = Field(pattern=SHA256_PATTERN)


class HarnessResult(StrictModel):
    status: HarnessStatus
    checks: tuple[str, ...]
    failures: tuple[str, ...] = ()


class EvidenceRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    goal: str = Field(min_length=1)
    field: str = Field(min_length=1)
    runtime: RuntimeInfo
    files: tuple[CapturedTextFile, ...] = ()
    feedback: tuple[str, ...] = ()
    harness: HarnessResult


class WorkflowManifest(StrictModel):
    graph: WorkflowGraph
    nodes: tuple[str, ...] = Field(min_length=1)


class PromotionCriteria(StrictModel):
    min_success_runs: int = Field(ge=1)
    max_human_intervention_rate: float = Field(ge=0.0, le=1.0)
    required_harness_pass_rate: float = Field(ge=0.0, le=1.0)


class CapabilityManifest(StrictModel):
    name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    description: str = Field(min_length=1)
    status: CapabilityStatus
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    normalized_goal: str = Field(min_length=1)
    inputs: tuple[str, ...]
    workflow: WorkflowManifest
    harness: HarnessResult
    runtime: RuntimeInfo
    promotion_criteria: PromotionCriteria


class ReplayRecord(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    source_goal: str = Field(min_length=1)
    workflow: WorkflowManifest
    harness: HarnessResult
    runtime: RuntimeInfo


class EvalCheck(StrictModel):
    name: str = Field(min_length=1)
    status: EvalStatus
    message: str = Field(min_length=1)


class EvalResult(StrictModel):
    id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    created_at: datetime
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source_evidence_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    replay_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    status: EvalStatus
    checks: tuple[EvalCheck, ...]
    failures: tuple[str, ...] = ()
