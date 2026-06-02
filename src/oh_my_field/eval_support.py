import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import TypedDict

from pydantic import Field

from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    EVIDENCE_ID_PATTERN,
    CommandExecution,
    EvalCheck,
    EvalChecklistItem,
    EvalResult,
    EvalRubricScore,
    EvidenceRecord,
    ReplayRecord,
    StrictModel,
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class EvalError(Exception):
    pass


@dataclass
class EvalStateError(EvalError):
    key: str

    def __str__(self) -> str:
        return f"eval workflow state missing {self.key!r}"


@dataclass
class CapabilityNameMismatchError(EvalError):
    requested_name: str
    manifest_name: str

    def __str__(self) -> str:
        return (
            f"manifest name {self.manifest_name!r} does not match requested "
            f"capability {self.requested_name!r}"
        )


@dataclass(frozen=True, slots=True)
class EvalDependencies:
    clock: Clock
    token_factory: TokenFactory


class EvalRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    replay_id: str | None = Field(default=None, pattern=EVIDENCE_ID_PATTERN)
    capabilities_dir: Path
    evidence_dir: Path
    replay_dir: Path
    eval_dir: Path
    harness_commands: tuple[str, ...] = ()
    checklist_items: tuple[EvalChecklistItem, ...] = ()
    rubric_scores: tuple[EvalRubricScore, ...] = ()
    command_cwd: Path = Path()
    command_timeout_seconds: int = Field(default=60, ge=1)


class EvalSummary(StrictModel):
    eval_id: str
    eval_path: str
    capability_name: str
    status: str


class EvalState(TypedDict, total=False):
    request: EvalRequest
    dependencies: EvalDependencies
    source_evidence: EvidenceRecord
    replay: ReplayRecord | None
    command_executions: tuple[CommandExecution, ...]
    result: EvalResult
    result_path: Path
    summary: EvalSummary
    manifest_source_evidence_id: str


def default_dependencies() -> EvalDependencies:
    return EvalDependencies(clock=_now_utc, token_factory=_token_suffix)


def build_comparison_check(
    *,
    name: str,
    expected: str,
    actual: str,
    label: str,
) -> EvalCheck:
    if actual == expected:
        return EvalCheck(
            name=name,
            status="pass",
            message=f"replay {label} matches {expected!r}",
        )
    return EvalCheck(
        name=name,
        status="fail",
        message=f"replay {label} {actual!r} does not match {expected!r}",
    )


def build_harness_check(*, name: str, subject: str, status: str) -> EvalCheck:
    if status == "pass":
        return EvalCheck(
            name=name,
            status="pass",
            message=f"{subject} harness passed",
        )
    return EvalCheck(
        name=name,
        status="fail",
        message=f"{subject} harness failed",
    )


def state_request(state: EvalState) -> EvalRequest:
    request = state.get("request")
    if request is None:
        raise EvalStateError(key="request")
    return request


def state_dependencies(state: EvalState) -> EvalDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise EvalStateError(key="dependencies")
    return dependencies


def state_manifest_source_evidence_id(state: EvalState) -> str:
    source_evidence_id = state.get("manifest_source_evidence_id")
    if source_evidence_id is None:
        raise EvalStateError(key="manifest_source_evidence_id")
    return source_evidence_id


def state_source_evidence(state: EvalState) -> EvidenceRecord:
    source_evidence = state.get("source_evidence")
    if source_evidence is None:
        raise EvalStateError(key="source_evidence")
    return source_evidence


def state_result(state: EvalState) -> EvalResult:
    result = state.get("result")
    if result is None:
        raise EvalStateError(key="result")
    return result


def state_result_path(state: EvalState) -> Path:
    result_path = state.get("result_path")
    if result_path is None:
        raise EvalStateError(key="result_path")
    return result_path


def state_summary(state: EvalState) -> EvalSummary:
    summary = state.get("summary")
    if summary is None:
        raise EvalStateError(key="summary")
    return summary


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)
