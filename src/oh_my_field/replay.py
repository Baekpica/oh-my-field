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
    CAPABILITY_NAME_PATTERN,
    CapabilityManifest,
    EvidenceRecord,
    ReplayRecord,
    StrictModel,
    WorkflowManifest,
)
from oh_my_field.storage import load_evidence, load_manifest, write_replay

REPLAY_NODES: Final = (
    "load_manifest",
    "load_source_evidence",
    "build_replay",
    "validate_replay",
    "write_replay",
    "summarize",
)

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class ReplayError(Exception):
    pass


@dataclass
class ReplayStateError(ReplayError):
    key: str

    def __str__(self) -> str:
        return f"replay workflow state missing {self.key!r}"


@dataclass
class CapabilityNameMismatchError(ReplayError):
    requested_name: str
    manifest_name: str

    def __str__(self) -> str:
        return (
            f"manifest name {self.manifest_name!r} does not match requested "
            f"capability {self.requested_name!r}"
        )


@dataclass(frozen=True, slots=True)
class ReplayDependencies:
    clock: Clock
    token_factory: TokenFactory


class ReplayRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    evidence_dir: Path
    replay_dir: Path


class ReplaySummary(StrictModel):
    replay_id: str
    replay_path: str
    capability_name: str
    harness_status: str


class ReplayState(TypedDict, total=False):
    request: ReplayRequest
    dependencies: ReplayDependencies
    manifest: CapabilityManifest
    source_evidence: EvidenceRecord
    replay: ReplayRecord
    replay_path: Path
    summary: ReplaySummary


def run_replay_workflow(
    request: ReplayRequest,
    dependencies: ReplayDependencies | None = None,
) -> ReplaySummary:
    graph = _build_replay_graph()
    initial_state = ReplayState(
        request=request,
        dependencies=dependencies or _default_dependencies(),
    )
    final_state = graph.invoke(initial_state)
    return _state_summary(final_state)


def _default_dependencies() -> ReplayDependencies:
    return ReplayDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _build_replay_graph() -> CompiledStateGraph[
    ReplayState,
    None,
    ReplayState,
    ReplayState,
]:
    builder: StateGraph[ReplayState, None, ReplayState, ReplayState] = StateGraph(
        ReplayState,
    )
    builder.add_node("load_manifest", _load_manifest)
    builder.add_node("load_source_evidence", _load_source_evidence)
    builder.add_node("build_replay", _build_replay)
    builder.add_node("validate_replay", _validate_replay)
    builder.add_node("write_replay", _write_replay)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "build_replay")
    builder.add_edge("build_replay", "validate_replay")
    builder.add_edge("validate_replay", "write_replay")
    builder.add_edge("write_replay", "summarize")
    builder.add_edge("summarize", END)
    return builder.compile()


def _load_manifest(state: ReplayState) -> ReplayState:
    request = _state_request(state)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    if manifest.name != request.capability_name:
        raise CapabilityNameMismatchError(
            requested_name=request.capability_name,
            manifest_name=manifest.name,
        )
    return ReplayState(manifest=manifest)


def _load_source_evidence(state: ReplayState) -> ReplayState:
    request = _state_request(state)
    manifest = _state_manifest(state)
    source_evidence = load_evidence(manifest.source_evidence_id, request.evidence_dir)
    return ReplayState(source_evidence=source_evidence)


def _build_replay(state: ReplayState) -> ReplayState:
    dependencies = _state_dependencies(state)
    manifest = _state_manifest(state)
    source_evidence = _state_source_evidence(state)
    created_at = dependencies.clock().astimezone(UTC)
    replay = ReplayRecord(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=manifest.name,
        source_evidence_id=source_evidence.id,
        source_goal=source_evidence.goal,
        workflow=WorkflowManifest(graph="langgraph", nodes=REPLAY_NODES),
        harness=source_evidence.harness,
        runtime=source_evidence.runtime,
    )
    return ReplayState(replay=replay)


def _validate_replay(state: ReplayState) -> ReplayState:
    replay = _state_replay(state)
    checked = ReplayRecord.model_validate(replay)
    return ReplayState(replay=checked)


def _write_replay(state: ReplayState) -> ReplayState:
    replay = _state_replay(state)
    request = _state_request(state)
    replay_path = write_replay(replay, request.replay_dir)
    return ReplayState(replay_path=replay_path)


def _summarize(state: ReplayState) -> ReplayState:
    replay = _state_replay(state)
    replay_path = _state_replay_path(state)
    summary = ReplaySummary(
        replay_id=replay.id,
        replay_path=str(replay_path),
        capability_name=replay.capability_name,
        harness_status=replay.harness.status,
    )
    return ReplayState(summary=summary)


def _state_request(state: ReplayState) -> ReplayRequest:
    request = state.get("request")
    if request is None:
        raise ReplayStateError(key="request")
    return request


def _state_dependencies(state: ReplayState) -> ReplayDependencies:
    dependencies = state.get("dependencies")
    if dependencies is None:
        raise ReplayStateError(key="dependencies")
    return dependencies


def _state_manifest(state: ReplayState) -> CapabilityManifest:
    manifest = state.get("manifest")
    if manifest is None:
        raise ReplayStateError(key="manifest")
    return manifest


def _state_source_evidence(state: ReplayState) -> EvidenceRecord:
    source_evidence = state.get("source_evidence")
    if source_evidence is None:
        raise ReplayStateError(key="source_evidence")
    return source_evidence


def _state_replay(state: ReplayState) -> ReplayRecord:
    replay = state.get("replay")
    if replay is None:
        raise ReplayStateError(key="replay")
    return replay


def _state_replay_path(state: ReplayState) -> Path:
    replay_path = state.get("replay_path")
    if replay_path is None:
        raise ReplayStateError(key="replay_path")
    return replay_path


def _state_summary(state: ReplayState) -> ReplaySummary:
    summary = state.get("summary")
    if summary is None:
        raise ReplayStateError(key="summary")
    return summary
