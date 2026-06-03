import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph
from pydantic import Field

from oh_my_field.execution import (
    CommandExecutionError,
    CommandExecutionRequest,
    execute_shell_command,
)
from oh_my_field.integrity import append_integrity_link, integrity_link
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    ArtifactIntegrityLink,
    CapabilityManifest,
    CommandExecution,
    EvidenceRecord,
    HarnessResult,
    ReplayRecord,
    RuntimeInfo,
    StrictModel,
    WorkflowManifest,
)
from oh_my_field.storage import load_evidence, load_manifest, write_replay

REPLAY_NODES: Final = (
    "load_manifest",
    "load_source_evidence",
    "execute_commands",
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
    execute_commands: bool = False
    command_cwd: Path = Path()
    command_timeout_seconds: int = Field(default=60, ge=1)
    approve_command_risk: bool = False
    runtime_profile: str | None = None


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
    command_executions: tuple[CommandExecution, ...]
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
    builder.add_node("execute_commands", _execute_commands)
    builder.add_node("build_replay", _build_replay)
    builder.add_node("validate_replay", _validate_replay)
    builder.add_node("write_replay", _write_replay)
    builder.add_node("summarize", _summarize)
    builder.add_edge(START, "load_manifest")
    builder.add_edge("load_manifest", "load_source_evidence")
    builder.add_edge("load_source_evidence", "execute_commands")
    builder.add_edge("execute_commands", "build_replay")
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


def _execute_commands(state: ReplayState) -> ReplayState:
    request = _state_request(state)
    source_evidence = _state_source_evidence(state)
    if not request.execute_commands:
        return ReplayState(command_executions=())
    manifest = _state_manifest(state)
    command_executions = tuple(
        _execute_command(command, request, manifest)
        for command in source_evidence.generated_commands
    )
    return ReplayState(command_executions=command_executions)


def _build_replay(state: ReplayState) -> ReplayState:
    request = _state_request(state)
    dependencies = _state_dependencies(state)
    manifest = _state_manifest(state)
    source_evidence = _state_source_evidence(state)
    command_executions = _state_command_executions(state)
    created_at = dependencies.clock().astimezone(UTC)
    command_failures = tuple(
        execution.stderr or f"command exited with {execution.exit_code}"
        for execution in command_executions
        if execution.exit_code != 0
    )
    harness = source_evidence.harness
    if command_executions:
        harness = HarnessResult(
            status="fail" if command_failures else "pass",
            checks=(*source_evidence.harness.checks, "commands_replayed"),
            failures=command_failures,
            required_checks=source_evidence.harness.required_checks,
            human_review_required=source_evidence.harness.human_review_required,
        )
    replay = ReplayRecord(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        capability_name=manifest.name,
        source_evidence_id=source_evidence.id,
        source_goal=source_evidence.goal,
        workflow=WorkflowManifest(graph="langgraph", nodes=REPLAY_NODES),
        harness=harness,
        runtime=_replay_runtime(source_evidence.runtime, request.runtime_profile),
        runtime_profile=request.runtime_profile,
        command_executions=command_executions,
    )
    replay = replay.model_copy(
        update={"integrity_chain": (_evidence_integrity_link(source_evidence),)},
    )
    replay = append_integrity_link(
        replay,
        artifact_type="replay",
        artifact_id=replay.id,
        previous_sha256=replay.integrity_chain[-1].sha256,
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


def _execute_command(
    command: str,
    request: ReplayRequest,
    manifest: CapabilityManifest,
) -> CommandExecution:
    try:
        return execute_shell_command(
            CommandExecutionRequest(
                command=command,
                cwd=request.command_cwd,
                timeout_seconds=request.command_timeout_seconds,
                approve_risk=request.approve_command_risk,
                approval_required_categories=(
                    manifest.workflow_control.approval_required_actions
                ),
            ),
        )
    except CommandExecutionError as exc:
        return CommandExecution(
            command=command,
            cwd=str(request.command_cwd),
            exit_code=1,
            stderr=str(exc),
            duration_ms=0,
        )


def _replay_runtime(
    runtime: RuntimeInfo,
    runtime_profile: str | None,
) -> RuntimeInfo:
    if runtime_profile is None:
        return runtime
    return runtime.model_copy(update={"name": runtime_profile})


def _evidence_integrity_link(evidence: EvidenceRecord) -> ArtifactIntegrityLink:
    if evidence.integrity_chain:
        return evidence.integrity_chain[-1]
    return integrity_link(
        artifact_type="evidence",
        artifact_id=evidence.id,
        model=evidence,
    )


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


def _state_command_executions(
    state: ReplayState,
) -> tuple[CommandExecution, ...]:
    command_executions = state.get("command_executions")
    if command_executions is None:
        raise ReplayStateError(key="command_executions")
    return command_executions


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
