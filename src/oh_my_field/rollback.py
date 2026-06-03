from dataclasses import dataclass
from pathlib import Path
from typing import Final

from pydantic import Field

from oh_my_field.models import (
    EVIDENCE_ID_PATTERN,
    StrictModel,
    WorkflowNodeResult,
    WorkflowRunRecord,
)
from oh_my_field.storage import load_workflow_run, write_workflow_run

ROLLBACK_NODES: Final = (
    "import_evidence",
    "promote_capability",
    "pack_context",
    "run_verification",
    "evaluate_capability",
    "record_learning_patch",
)
ROLLBACK_NODE_ALIASES: Final = {
    "observe_capture": "import_evidence",
    "structure_promote": "promote_capability",
    "context_pack": "pack_context",
    "execute_replay": "run_verification",
    "evaluate_harness": "evaluate_capability",
    "learn_export": "record_learning_patch",
}


class RollbackError(Exception):
    pass


@dataclass
class UnknownRollbackNodeError(RollbackError):
    node: str

    def __str__(self) -> str:
        return f"unknown rollback node {self.node!r}"


class RollbackRequest(StrictModel):
    run_id: str = Field(pattern=EVIDENCE_ID_PATTERN)
    to_node: str = Field(min_length=1)
    reason: str = Field(default="manual rollback", min_length=1)
    workflow_dir: Path


class RollbackSummary(StrictModel):
    run_id: str
    run_path: str
    status: str
    current_node: str
    completed_nodes: tuple[str, ...]
    cleared_artifacts: tuple[str, ...]


def rollback_workflow(request: RollbackRequest) -> RollbackSummary:
    record = load_workflow_run(request.run_id, request.workflow_dir)
    rolled_back, cleared_artifacts = _rollback_record(record, request)
    run_path = write_workflow_run(rolled_back, request.workflow_dir)
    return RollbackSummary(
        run_id=rolled_back.id,
        run_path=str(run_path),
        status=rolled_back.status,
        current_node=rolled_back.current_node or request.to_node,
        completed_nodes=rolled_back.completed_nodes,
        cleared_artifacts=cleared_artifacts,
    )


def _rollback_record(
    record: WorkflowRunRecord,
    request: RollbackRequest,
) -> tuple[WorkflowRunRecord, tuple[str, ...]]:
    target_node = _canonical_node(request.to_node)
    target_index = _node_index(target_node)
    completed_node_names = {_canonical_node(node) for node in record.completed_nodes}
    completed_nodes = tuple(
        node for node in ROLLBACK_NODES[:target_index] if node in completed_node_names
    )
    updates, cleared_artifacts = _artifact_resets(record, target_index)
    rollback_note = WorkflowNodeResult(
        name=f"rollback_to_{target_node}",
        status="pass",
        message=f"rolled back to {target_node}: {request.reason}",
    )
    rolled_back = record.model_copy(
        update={
            "status": "pending_review",
            "current_node": target_node,
            "completed_nodes": completed_nodes,
            "failed_node": None,
            "failure_reason": None,
            "nodes": (*record.nodes, rollback_note),
            **updates,
        },
    )
    return rolled_back, cleared_artifacts


def _node_index(node: str) -> int:
    try:
        return ROLLBACK_NODES.index(node)
    except ValueError as exc:
        raise UnknownRollbackNodeError(node=node) from exc


def _canonical_node(node: str) -> str:
    return ROLLBACK_NODE_ALIASES.get(node, node)


def _artifact_resets(
    record: WorkflowRunRecord,
    target_index: int,
) -> tuple[dict[str, None], tuple[str, ...]]:
    artifact_fields = (
        ("evidence_id", 0, record.evidence_id),
        ("capability_name", 1, record.capability_name),
        ("context_id", 2, record.context_id),
        ("replay_id", 3, record.replay_id),
        ("eval_id", 4, record.eval_id),
        ("learning_id", 5, record.learning_id),
    )
    updates: dict[str, None] = {}
    cleared: list[str] = []
    for field_name, field_index, value in artifact_fields:
        if field_index >= target_index and value is not None:
            updates[field_name] = None
            cleared.append(field_name)
    return updates, tuple(cleared)
