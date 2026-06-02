import hashlib
import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.models import (
    CapturedFileRole,
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
    StrictModel,
)
from oh_my_field.storage import write_evidence

CAPTURE_NODES: Final = (
    "collect_files",
    "build_evidence",
    "validate_harness",
    "persist_evidence",
    "summarize",
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class CaptureError(Exception):
    pass


@dataclass
class CaptureStateError(CaptureError):
    key: str

    def __str__(self) -> str:
        return f"capture workflow state missing {self.key!r}"


@dataclass
class InputFileReadError(CaptureError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not read input file {self.path}: {self.reason}"


@dataclass(frozen=True, slots=True)
class CaptureDependencies:
    clock: Clock
    token_factory: TokenFactory


class CaptureFileInput(StrictModel):
    role: CapturedFileRole
    path: Path


class CaptureRequest(StrictModel):
    goal: str = Field(min_length=1)
    field: str = Field(min_length=1)
    runtime: str = Field(min_length=1)
    model: str | None = None
    evidence_dir: Path
    files: tuple[CaptureFileInput, ...] = ()
    feedback: tuple[str, ...] = ()


class CaptureSummary(StrictModel):
    evidence_id: str
    evidence_path: str
    harness_status: str


class CaptureState(TypedDict, total=False):
    request: CaptureRequest
    dependencies: CaptureDependencies
    captured_files: tuple[CapturedTextFile, ...]
    evidence: EvidenceRecord
    evidence_path: Path
    summary: CaptureSummary


def run_capture_workflow(
    request: CaptureRequest,
    dependencies: CaptureDependencies | None = None,
) -> CaptureSummary:
    graph = _build_capture_graph()
    initial_state = CaptureState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _default_dependencies() -> CaptureDependencies:
    return CaptureDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _build_capture_graph() -> CompiledStateGraph[
    CaptureState,
    None,
    CaptureState,
    CaptureState,
]:
    builder: StateGraph[CaptureState, None, CaptureState, CaptureState] = StateGraph(
        CaptureState,
    )
    builder.add_node("collect_files", _collect_files)
    builder.add_node("build_evidence", _build_evidence)
    builder.add_node("validate_harness", _validate_harness)
    builder.add_node("persist_evidence", _persist_evidence)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "collect_files")
    builder.add_edge("collect_files", "build_evidence")
    builder.add_edge("build_evidence", "validate_harness")
    builder.add_edge("validate_harness", "persist_evidence")
    builder.add_edge("persist_evidence", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _collect_files(state: CaptureState) -> CaptureState:
    request = _state_request(state)
    captured_files = tuple(
        _read_text_file(file_input) for file_input in request.files
    )
    return CaptureState(captured_files=captured_files)


def _build_evidence(state: CaptureState) -> CaptureState:
    request = _state_request(state)
    dependencies = _state_dependencies(state)
    created_at = dependencies.clock().astimezone(UTC)
    evidence = EvidenceRecord(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        goal=request.goal,
        field=request.field,
        runtime=RuntimeInfo(name=request.runtime, model=request.model),
        files=_state_captured_files(state),
        feedback=request.feedback,
        harness=HarnessResult(status="pass", checks=("files_readable",), failures=()),
    )
    return CaptureState(evidence=evidence)


def _validate_harness(state: CaptureState) -> CaptureState:
    evidence = _state_evidence(state)
    checked = EvidenceRecord.model_validate(evidence)
    harness = HarnessResult(
        status="pass",
        checks=(*checked.harness.checks, "schema_valid"),
        failures=(),
    )
    return CaptureState(evidence=checked.model_copy(update={"harness": harness}))


def _persist_evidence(state: CaptureState) -> CaptureState:
    evidence = _state_evidence(state)
    request = _state_request(state)
    evidence_path = write_evidence(evidence, request.evidence_dir)
    return CaptureState(evidence_path=evidence_path)


def _summarize(state: CaptureState) -> CaptureState:
    evidence = _state_evidence(state)
    evidence_path = _state_evidence_path(state)
    summary = CaptureSummary(
        evidence_id=evidence.id,
        evidence_path=str(evidence_path),
        harness_status=evidence.harness.status,
    )
    return CaptureState(summary=summary)


def _read_text_file(file_input: CaptureFileInput) -> CapturedTextFile:
    try:
        raw_content = file_input.path.read_bytes()
    except OSError as exc:
        raise InputFileReadError(path=file_input.path, reason=str(exc)) from exc

    try:
        content = raw_content.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise InputFileReadError(
            path=file_input.path,
            reason="not valid UTF-8",
        ) from exc

    return CapturedTextFile(
        role=file_input.role,
        path=str(file_input.path),
        content=content,
        size_bytes=len(raw_content),
        sha256=hashlib.sha256(raw_content).hexdigest(),
    )


def _state_request(state: CaptureState) -> CaptureRequest:
    request = state.get("request")
    if request is None:
        raise CaptureStateError(key="request")
    return request


def _state_dependencies(state: CaptureState) -> CaptureDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise CaptureStateError(key="dependencies")
    return dependencies


def _state_captured_files(state: CaptureState) -> tuple[CapturedTextFile, ...]:
    captured_files = state.get("captured_files")
    if captured_files is None:
        raise CaptureStateError(key="captured_files")
    return captured_files


def _state_evidence(state: CaptureState) -> EvidenceRecord:
    evidence = state.get("evidence")
    if evidence is None:
        raise CaptureStateError(key="evidence")
    return evidence


def _state_evidence_path(state: CaptureState) -> Path:
    evidence_path = state.get("evidence_path")
    if evidence_path is None:
        raise CaptureStateError(key="evidence_path")
    return evidence_path


def _state_summary(state: CaptureState) -> CaptureSummary:
    summary = state.get("summary")
    if summary is None:
        raise CaptureStateError(key="summary")
    return summary
