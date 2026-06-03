import secrets
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final

from pydantic import Field, ValidationError

from oh_my_field.capture import (
    CaptureError,
    CaptureFileInput,
    CaptureRequest,
    run_capture_workflow,
)
from oh_my_field.context import ContextError, ContextRequest, run_context_workflow
from oh_my_field.eval import EvalError, EvalRequest, run_eval_workflow
from oh_my_field.learn import LearnError, LearnRequest, run_learn_workflow
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    EvalChecklistItem,
    EvalRubricScore,
    StrictModel,
    WorkflowFileInput,
    WorkflowNodeResult,
    WorkflowRunConfig,
    WorkflowRunRecord,
)
from oh_my_field.promote import PromoteError, PromoteRequest, run_promote_workflow
from oh_my_field.replay import ReplayError, ReplayRequest, run_replay_workflow
from oh_my_field.storage import (
    StorageError,
    load_workflow_run,
    write_workflow_run,
)

ORCHESTRATOR_NODES: Final = (
    "import_evidence",
    "promote_capability",
    "pack_context",
    "run_verification",
    "evaluate_capability",
    "record_learning_patch",
)
NODE_ALIASES: Final = {
    "observe_capture": "import_evidence",
    "structure_promote": "promote_capability",
    "context_pack": "pack_context",
    "execute_replay": "run_verification",
    "evaluate_harness": "evaluate_capability",
    "learn_export": "record_learning_patch",
}

type Clock = Callable[[], datetime]
type TokenFactory = Callable[[], str]


class OrchestrateError(Exception):
    pass


@dataclass
class UnknownOrchestratorNodeError(OrchestrateError):
    node: str

    def __str__(self) -> str:
        return f"unknown orchestrator node {self.node!r}"


@dataclass
class NodeResultMissingError(OrchestrateError):
    node: str

    def __str__(self) -> str:
        return f"node {self.node!r} did not record a result"


@dataclass
class RequiredWorkflowValueMissingError(OrchestrateError):
    key: str

    def __str__(self) -> str:
        return f"workflow missing required {self.key}"


@dataclass(frozen=True, slots=True)
class OrchestrateDependencies:
    clock: Clock
    token_factory: TokenFactory


class OrchestrateRequest(StrictModel):
    goal: str = Field(min_length=1)
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    description: str = Field(min_length=1)
    version: str = Field(default="0.1.0", min_length=1)
    field: str = Field(default="local", min_length=1)
    runtime: str = Field(default="codex", min_length=1)
    model: str | None = None
    runtime_tools: tuple[str, ...] = ()
    files: tuple[CaptureFileInput, ...] = ()
    commands: tuple[str, ...] = ()
    command_cwd: Path = Path()
    command_timeout_seconds: int = Field(default=60, ge=1)
    approve_command_risk: bool = False
    harness_commands: tuple[str, ...] = ()
    checklist_items: tuple[EvalChecklistItem, ...] = ()
    rubric_scores: tuple[EvalRubricScore, ...] = ()
    execute_replay_commands: bool = True
    include_optional_context: bool = True
    allow_failed_capture: bool = False
    evidence_dir: Path = Path(".omf/evidence")
    capabilities_dir: Path = Path("capabilities")
    replay_dir: Path = Path(".omf/replays")
    eval_dir: Path = Path(".omf/evals")
    context_dir: Path = Path(".omf/context")
    learning_dir: Path = Path(".omf/learning")
    workflow_dir: Path = Path(".omf/workflows")


class ResumeRequest(StrictModel):
    run_id: str = Field(min_length=1)
    workflow_dir: Path = Path(".omf/workflows")


class WorkflowRunSummary(StrictModel):
    run_id: str
    run_path: str
    status: str
    current_node: str | None
    evidence_id: str | None = None
    capability_name: str | None = None
    replay_id: str | None = None
    eval_id: str | None = None
    context_id: str | None = None
    learning_id: str | None = None
    failure_reason: str | None = None


def run_orchestrate_workflow(
    request: OrchestrateRequest,
    dependencies: OrchestrateDependencies | None = None,
) -> WorkflowRunSummary:
    dependencies = dependencies or _default_dependencies()
    created_at = dependencies.clock().astimezone(UTC)
    record = WorkflowRunRecord(
        id=f"{created_at:%Y%m%dT%H%M%SZ}-{dependencies.token_factory()}",
        created_at=created_at,
        updated_at=created_at,
        goal=request.goal,
        status="running",
        current_node=ORCHESTRATOR_NODES[0],
        config=_config_from_request(request),
    )
    write_workflow_run(record, request.workflow_dir)
    return _continue_workflow(record, request.workflow_dir, dependencies)


def run_resume_workflow(
    request: ResumeRequest,
    dependencies: OrchestrateDependencies | None = None,
) -> WorkflowRunSummary:
    dependencies = dependencies or _default_dependencies()
    record = load_workflow_run(request.run_id, request.workflow_dir)
    if record.status == "completed":
        return _summary(record, request.workflow_dir)
    resumed = record.model_copy(
        update={
            "status": "running",
            "failed_node": None,
            "failure_reason": None,
        },
    )
    write_workflow_run(
        _touch(resumed, dependencies.clock().astimezone(UTC)),
        request.workflow_dir,
    )
    return _continue_workflow(resumed, request.workflow_dir, dependencies)


def load_workflow_summary(run_id: str, workflow_dir: Path) -> WorkflowRunSummary:
    return _summary(load_workflow_run(run_id, workflow_dir), workflow_dir)


def _default_dependencies() -> OrchestrateDependencies:
    return OrchestrateDependencies(clock=_now_utc, token_factory=_token_suffix)


def _now_utc() -> datetime:
    return datetime.now(UTC)


def _token_suffix() -> str:
    return secrets.token_hex(4)


def _continue_workflow(
    record: WorkflowRunRecord,
    workflow_dir: Path,
    dependencies: OrchestrateDependencies,
) -> WorkflowRunSummary:
    current = record
    for node in ORCHESTRATOR_NODES:
        if node in _completed_node_names(current):
            continue
        current = _checkpoint(
            current.model_copy(update={"current_node": node, "status": "running"}),
            workflow_dir,
            dependencies,
        )
        try:
            current = _run_node(current, node)
        except (
            CaptureError,
            ContextError,
            EvalError,
            LearnError,
            PromoteError,
            ReplayError,
            StorageError,
            ValidationError,
            OrchestrateError,
        ) as exc:
            current = _fail_node(current, node, str(exc), workflow_dir, dependencies)
            return _summary(current, workflow_dir)

        node_result = _latest_node_result(current, node)
        current = _checkpoint(current, workflow_dir, dependencies)
        if node_result.status == "fail":
            current = _fail_node(
                current,
                node,
                node_result.message,
                workflow_dir,
                dependencies,
            )
            return _summary(current, workflow_dir)

    completed = current.model_copy(
        update={"status": "completed", "current_node": None},
    )
    completed = _checkpoint(completed, workflow_dir, dependencies)
    return _summary(completed, workflow_dir)


def _run_node(record: WorkflowRunRecord, node: str) -> WorkflowRunRecord:
    node = _canonical_node(node)
    if node == "import_evidence":
        return _run_capture_node(record)
    if node == "promote_capability":
        return _run_promote_node(record)
    if node == "pack_context":
        return _run_context_node(record)
    if node == "run_verification":
        return _run_replay_node(record)
    if node == "evaluate_capability":
        return _run_eval_node(record)
    if node == "record_learning_patch":
        return _run_learn_node(record)
    raise UnknownOrchestratorNodeError(node=node)


def _run_capture_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    summary = run_capture_workflow(
        CaptureRequest(
            goal=record.goal,
            field=config.field,
            runtime=config.runtime,
            model=config.model,
            runtime_tools=config.runtime_tools,
            evidence_dir=Path(config.evidence_dir),
            files=_capture_files(config.files),
            commands=config.commands,
            command_cwd=Path(config.command_cwd),
            command_timeout_seconds=config.command_timeout_seconds,
            approve_command_risk=config.approve_command_risk,
        ),
    )
    status = "pass"
    message = f"captured evidence {summary.evidence_id!r}"
    if summary.harness_status == "fail" and not config.allow_failed_capture:
        status = "fail"
        message = f"capture harness failed for evidence {summary.evidence_id!r}"
    return _record_node(
        record.model_copy(update={"evidence_id": summary.evidence_id}),
        WorkflowNodeResult(
            name="import_evidence",
            status=status,
            message=message,
            path=summary.evidence_path,
        ),
    )


def _run_promote_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    evidence_id = _required_id(record.evidence_id, "evidence_id")
    summary = run_promote_workflow(
        PromoteRequest(
            evidence_id=evidence_id,
            name=config.capability_name,
            description=config.description,
            version=config.version,
            evidence_dir=Path(config.evidence_dir),
            capabilities_dir=Path(config.capabilities_dir),
        ),
    )
    return _record_node(
        record.model_copy(update={"capability_name": summary.capability_name}),
        WorkflowNodeResult(
            name="promote_capability",
            status="pass",
            message=f"promoted capability {summary.capability_name!r}",
            path=summary.manifest_path,
        ),
    )


def _run_context_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    capability_name = _required_id(record.capability_name, "capability_name")
    summary = run_context_workflow(
        ContextRequest(
            capability_name=capability_name,
            capabilities_dir=Path(config.capabilities_dir),
            evidence_dir=Path(config.evidence_dir),
            context_dir=Path(config.context_dir),
            include_optional=config.include_optional_context,
        ),
    )
    return _record_node(
        record.model_copy(update={"context_id": summary.context_id}),
        WorkflowNodeResult(
            name="pack_context",
            status="pass",
            message=f"packed context {summary.context_id!r}",
            path=summary.context_path,
        ),
    )


def _run_replay_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    capability_name = _required_id(record.capability_name, "capability_name")
    summary = run_replay_workflow(
        ReplayRequest(
            capability_name=capability_name,
            capabilities_dir=Path(config.capabilities_dir),
            evidence_dir=Path(config.evidence_dir),
            replay_dir=Path(config.replay_dir),
            execute_commands=config.execute_replay_commands,
            command_cwd=Path(config.command_cwd),
            command_timeout_seconds=config.command_timeout_seconds,
            approve_command_risk=config.approve_command_risk,
        ),
    )
    status = "pass" if summary.harness_status == "pass" else "fail"
    return _record_node(
        record.model_copy(update={"replay_id": summary.replay_id}),
        WorkflowNodeResult(
            name="run_verification",
            status=status,
            message=(
                f"replayed capability {summary.capability_name!r} "
                f"with harness {summary.harness_status!r}"
            ),
            path=summary.replay_path,
        ),
    )


def _run_eval_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    capability_name = _required_id(record.capability_name, "capability_name")
    summary = run_eval_workflow(
        EvalRequest(
            capability_name=capability_name,
            replay_id=record.replay_id,
            capabilities_dir=Path(config.capabilities_dir),
            evidence_dir=Path(config.evidence_dir),
            replay_dir=Path(config.replay_dir),
            eval_dir=Path(config.eval_dir),
            harness_commands=config.harness_commands,
            checklist_items=config.checklist_items,
            rubric_scores=config.rubric_scores,
            command_cwd=Path(config.command_cwd),
            command_timeout_seconds=config.command_timeout_seconds,
            approve_command_risk=config.approve_command_risk,
        ),
    )
    return _record_node(
        record.model_copy(update={"eval_id": summary.eval_id}),
        WorkflowNodeResult(
            name="evaluate_capability",
            status="pass" if summary.status == "pass" else "fail",
            message=f"evaluated capability with status {summary.status!r}",
            path=summary.eval_path,
        ),
    )


def _run_learn_node(record: WorkflowRunRecord) -> WorkflowRunRecord:
    config = record.config
    capability_name = _required_id(record.capability_name, "capability_name")
    summary = run_learn_workflow(
        LearnRequest(
            capability_name=capability_name,
            capabilities_dir=Path(config.capabilities_dir),
            evidence_dir=Path(config.evidence_dir),
            learning_dir=Path(config.learning_dir),
        ),
    )
    return _record_node(
        record.model_copy(update={"learning_id": summary.learning_id}),
        WorkflowNodeResult(
            name="record_learning_patch",
            status="pass",
            message=f"exported learning asset {summary.learning_id!r}",
            path=summary.learning_path,
        ),
    )


def _config_from_request(request: OrchestrateRequest) -> WorkflowRunConfig:
    return WorkflowRunConfig(
        capability_name=request.capability_name,
        description=request.description,
        version=request.version,
        field=request.field,
        runtime=request.runtime,
        model=request.model,
        runtime_tools=request.runtime_tools,
        files=tuple(
            WorkflowFileInput(role=file.role, path=str(file.path))
            for file in request.files
        ),
        commands=request.commands,
        command_cwd=str(request.command_cwd),
        command_timeout_seconds=request.command_timeout_seconds,
        approve_command_risk=request.approve_command_risk,
        harness_commands=request.harness_commands,
        checklist_items=request.checklist_items,
        rubric_scores=request.rubric_scores,
        execute_replay_commands=request.execute_replay_commands,
        include_optional_context=request.include_optional_context,
        allow_failed_capture=request.allow_failed_capture,
        evidence_dir=str(request.evidence_dir),
        capabilities_dir=str(request.capabilities_dir),
        replay_dir=str(request.replay_dir),
        eval_dir=str(request.eval_dir),
        context_dir=str(request.context_dir),
        learning_dir=str(request.learning_dir),
    )


def _capture_files(
    files: tuple[WorkflowFileInput, ...],
) -> tuple[CaptureFileInput, ...]:
    return tuple(
        CaptureFileInput(role=file.role, path=Path(file.path)) for file in files
    )


def _record_node(
    record: WorkflowRunRecord,
    result: WorkflowNodeResult,
) -> WorkflowRunRecord:
    completed_nodes = record.completed_nodes
    if result.status == "pass" and result.name not in _completed_node_names(record):
        completed_nodes = (*completed_nodes, result.name)
    return record.model_copy(
        update={
            "completed_nodes": completed_nodes,
            "nodes": (*record.nodes, result),
        },
    )


def _checkpoint(
    record: WorkflowRunRecord,
    workflow_dir: Path,
    dependencies: OrchestrateDependencies,
) -> WorkflowRunRecord:
    updated = _touch(record, dependencies.clock().astimezone(UTC))
    write_workflow_run(updated, workflow_dir)
    return updated


def _touch(record: WorkflowRunRecord, updated_at: datetime) -> WorkflowRunRecord:
    return record.model_copy(update={"updated_at": updated_at})


def _canonical_node(node: str) -> str:
    return NODE_ALIASES.get(node, node)


def _completed_node_names(record: WorkflowRunRecord) -> set[str]:
    return {_canonical_node(node) for node in record.completed_nodes}


def _fail_node(
    record: WorkflowRunRecord,
    node: str,
    reason: str,
    workflow_dir: Path,
    dependencies: OrchestrateDependencies,
) -> WorkflowRunRecord:
    failed = record.model_copy(
        update={
            "status": "failed",
            "current_node": None,
            "failed_node": node,
            "failure_reason": reason,
        },
    )
    return _checkpoint(failed, workflow_dir, dependencies)


def _latest_node_result(
    record: WorkflowRunRecord,
    node: str,
) -> WorkflowNodeResult:
    for result in reversed(record.nodes):
        if result.name == node:
            return result
    raise NodeResultMissingError(node=node)


def _required_id(value: str | None, key: str) -> str:
    if value is None:
        raise RequiredWorkflowValueMissingError(key=key)
    return value


def _summary(record: WorkflowRunRecord, workflow_dir: Path) -> WorkflowRunSummary:
    return WorkflowRunSummary(
        run_id=record.id,
        run_path=str(workflow_dir / f"{record.id}.json"),
        status=record.status,
        current_node=record.current_node,
        evidence_id=record.evidence_id,
        capability_name=record.capability_name,
        replay_id=record.replay_id,
        eval_id=record.eval_id,
        context_id=record.context_id,
        learning_id=record.learning_id,
        failure_reason=record.failure_reason,
    )
