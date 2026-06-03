import re
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import Field

from oh_my_field.models import CAPABILITY_NAME_PATTERN, EVIDENCE_ID_PATTERN, StrictModel
from oh_my_field.storage import (
    load_context_bundle,
    load_eval_result,
    load_evidence,
    load_learning_export,
    load_manifest,
    load_reflection_report,
    load_replay,
    load_workflow_run,
    manifest_path_for_capability,
)

type InspectTargetType = Literal[
    "evidence",
    "capability",
    "replay",
    "eval",
    "workflow",
    "context",
    "learning",
    "reflection",
]
type JsonValue = (
    str | int | float | bool | None | list["JsonValue"] | dict[str, "JsonValue"]
)


class InspectRequest(StrictModel):
    target_type: InspectTargetType
    target_id: str = Field(min_length=1)
    capabilities_dir: Path
    evidence_dir: Path
    replay_dir: Path
    eval_dir: Path
    workflow_dir: Path
    context_dir: Path
    learning_dir: Path
    reflection_dir: Path


class InspectSummary(StrictModel):
    target_type: InspectTargetType
    target_id: str
    path: str
    status: str | None = None
    payload: dict[str, JsonValue]


@dataclass
class InvalidInspectTargetError(ValueError):
    target_kind: str
    value: str

    def __str__(self) -> str:
        return f"invalid {self.target_kind} {self.value!r}"


def inspect_artifact(request: InspectRequest) -> InspectSummary:
    inspectors = {
        "capability": _inspect_capability,
        "evidence": _inspect_evidence,
        "replay": _inspect_replay,
        "eval": _inspect_eval,
        "workflow": _inspect_workflow,
        "context": _inspect_context,
        "learning": _inspect_learning,
        "reflection": _inspect_reflection,
    }
    return inspectors[request.target_type](request)


def _inspect_capability(request: InspectRequest) -> InspectSummary:
    capability_name = _capability_name(request.target_id)
    manifest = load_manifest(capability_name, request.capabilities_dir)
    manifest_path = manifest_path_for_capability(
        capability_name,
        request.capabilities_dir,
    )
    return InspectSummary(
        target_type="capability",
        target_id=manifest.name,
        path=str(manifest_path or request.capabilities_dir / manifest.name),
        status=manifest.status,
        payload={
            "version": manifest.version,
            "source_evidence_id": manifest.source_evidence_id,
            "package_path": str(request.capabilities_dir / manifest.name),
            "capability_path": str(
                request.capabilities_dir / manifest.name / "capability.yaml",
            ),
            "card_path": str(request.capabilities_dir / manifest.name / "README.md"),
            "workflow_nodes": list(manifest.workflow.nodes),
            "runtime_tools": list(manifest.runtime.tools),
            "approval_required_actions": list(
                manifest.workflow_control.approval_required_actions,
            ),
        },
    )


def _inspect_evidence(request: InspectRequest) -> InspectSummary:
    evidence = load_evidence(_artifact_id(request.target_id), request.evidence_dir)
    return InspectSummary(
        target_type="evidence",
        target_id=evidence.id,
        path=str(request.evidence_dir / f"{evidence.id}.json"),
        status=evidence.harness.status,
        payload={
            "goal": evidence.goal,
            "runtime": evidence.runtime.name,
            "model": evidence.runtime.model,
            "command_count": len(evidence.command_executions),
            "file_count": len(evidence.files),
            "success_or_failure_label": evidence.success_or_failure_label,
        },
    )


def _inspect_replay(request: InspectRequest) -> InspectSummary:
    replay = load_replay(_artifact_id(request.target_id), request.replay_dir)
    return InspectSummary(
        target_type="replay",
        target_id=replay.id,
        path=str(request.replay_dir / f"{replay.id}.json"),
        status=replay.harness.status,
        payload={
            "capability_name": replay.capability_name,
            "source_evidence_id": replay.source_evidence_id,
            "command_count": len(replay.command_executions),
        },
    )


def _inspect_eval(request: InspectRequest) -> InspectSummary:
    result = load_eval_result(_artifact_id(request.target_id), request.eval_dir)
    return InspectSummary(
        target_type="eval",
        target_id=result.id,
        path=str(request.eval_dir / f"{result.id}.json"),
        status=result.status,
        payload={
            "capability_name": result.capability_name,
            "source_evidence_id": result.source_evidence_id,
            "replay_id": result.replay_id,
            "failure_count": len(result.failures),
        },
    )


def _inspect_workflow(request: InspectRequest) -> InspectSummary:
    run = load_workflow_run(_artifact_id(request.target_id), request.workflow_dir)
    return InspectSummary(
        target_type="workflow",
        target_id=run.id,
        path=str(request.workflow_dir / f"{run.id}.json"),
        status=run.status,
        payload={
            "goal": run.goal,
            "current_node": run.current_node,
            "completed_nodes": list(run.completed_nodes),
            "failed_node": run.failed_node,
            "failure_reason": run.failure_reason,
        },
    )


def _inspect_context(request: InspectRequest) -> InspectSummary:
    bundle = load_context_bundle(_artifact_id(request.target_id), request.context_dir)
    return InspectSummary(
        target_type="context",
        target_id=bundle.id,
        path=str(request.context_dir / f"{bundle.id}.json"),
        status=None,
        payload={
            "capability_name": bundle.capability_name,
            "required_count": len(bundle.required_context),
            "optional_count": len(bundle.optional_context),
            "summary_count": len(bundle.summaries),
        },
    )


def _inspect_learning(request: InspectRequest) -> InspectSummary:
    export = load_learning_export(_artifact_id(request.target_id), request.learning_dir)
    return InspectSummary(
        target_type="learning",
        target_id=export.id,
        path=str(request.learning_dir / f"{export.id}.json"),
        status=None,
        payload={
            "capability_name": export.capability_name,
            "prompt_patch_count": len(export.prompt_patches),
            "eval_set_candidate_count": len(export.eval_set_candidates),
            "fine_tuning_candidate_count": len(export.fine_tuning_candidates),
        },
    )


def _inspect_reflection(request: InspectRequest) -> InspectSummary:
    report = load_reflection_report(
        _artifact_id(request.target_id),
        request.reflection_dir,
    )
    return InspectSummary(
        target_type="reflection",
        target_id=report.id,
        path=str(request.reflection_dir / f"{report.id}.json"),
        status=None,
        payload={
            "capability_name": report.capability_name,
            "source_evidence_id": report.source_evidence_id,
            "eval_id": report.eval_id,
            "failure_categories": list(report.failure_categories),
        },
    )


def _artifact_id(value: str) -> str:
    if not re.fullmatch(EVIDENCE_ID_PATTERN, value):
        raise InvalidInspectTargetError(target_kind="artifact id", value=value)
    return value


def _capability_name(value: str) -> str:
    if not re.fullmatch(CAPABILITY_NAME_PATTERN, value):
        raise InvalidInspectTargetError(target_kind="capability name", value=value)
    return value
