from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from oh_my_field.application.health import CapabilityHealthRequest, run_health_workflow
from oh_my_field.application.portability import export_capability_package
from oh_my_field.application.promote import PromoteRequest, run_promote_workflow
from oh_my_field.application.session import (
    finish_session,
    materialize_session,
    record_session_event,
    start_session,
)
from oh_my_field.domain.models import StrictModel
from oh_my_field.domain.portability.models import CapabilityPortabilityExportRequest
from oh_my_field.mcp.schemas import (
    ExportCapabilityToolRequest,
    FinishSessionToolRequest,
    HealthToolRequest,
    MaterializeSessionToolRequest,
    McpToolDefinition,
    PromoteCapabilityToolRequest,
    RecordEventToolRequest,
    StartSessionToolRequest,
)

type ToolHandler = Callable[[object], StrictModel]


@dataclass(frozen=True, slots=True)
class ToolSpec:
    name: str
    description: str
    request_model: type[StrictModel]
    handler: ToolHandler


def dispatch_tool(name: str, arguments: object) -> dict[str, object]:
    spec = _tool_specs_by_name().get(name)
    if spec is None:
        msg = f"unknown OMF MCP tool {name!r}"
        raise KeyError(msg)
    return _summary(spec.handler(arguments))


def mcp_tool_definitions() -> tuple[dict[str, object], ...]:
    return tuple(
        {
            "name": definition.name,
            "description": definition.description,
            "inputSchema": definition.input_schema,
        }
        for definition in omf_tool_definitions()
    )


def omf_tool_definitions() -> tuple[McpToolDefinition, ...]:
    return tuple(
        McpToolDefinition(
            name=spec.name,
            description=spec.description,
            input_schema=cast(
                "dict[str, object]",
                spec.request_model.model_json_schema(),
            ),
        )
        for spec in TOOL_SPECS
    )


def _start_session(arguments: object) -> StrictModel:
    request = StartSessionToolRequest.model_validate(arguments)
    return start_session(
        runtime=request.runtime,
        model=request.model,
        project_root=request.project_root,
        activation_source="mcp",
        goal=request.goal,
        sessions_dir=request.sessions_dir,
    )


def _record_event(arguments: object) -> StrictModel:
    request = RecordEventToolRequest.model_validate(arguments)
    return record_session_event(
        session_id=request.session_id,
        event_type=request.type,
        summary=request.summary,
        path=request.artifact_path,
        command=request.command,
        exit_code=request.exit_code,
        risk_categories=request.risk_categories,
        sessions_dir=request.sessions_dir,
    )


def _finish_session(arguments: object) -> StrictModel:
    request = FinishSessionToolRequest.model_validate(arguments)
    return finish_session(
        session_id=request.session_id,
        outcome=request.outcome,
        sessions_dir=request.sessions_dir,
    )


def _materialize_session(arguments: object) -> StrictModel:
    request = MaterializeSessionToolRequest.model_validate(arguments)
    return materialize_session(
        session_id=request.session_id,
        sessions_dir=request.sessions_dir,
        evidence_dir=request.evidence_dir,
    )


def _promote_capability(arguments: object) -> StrictModel:
    request = PromoteCapabilityToolRequest.model_validate(arguments)
    return run_promote_workflow(
        PromoteRequest(
            evidence_id=request.evidence_id,
            name=request.name,
            description=request.description,
            version=request.version,
            evidence_dir=request.evidence_dir,
            eval_dir=request.eval_dir,
            capabilities_dir=request.capabilities_dir,
        ),
    )


def _export_capability(arguments: object) -> StrictModel:
    request = ExportCapabilityToolRequest.model_validate(arguments)
    return export_capability_package(
        CapabilityPortabilityExportRequest(
            capability_name=request.capability_name,
            target=request.target,
            target_model=request.target_model,
            target_project=request.target_project,
            source_project=request.source_project,
            source_reasoning_effort=request.source_reasoning_effort,
            source_context_tokens=request.source_context_tokens,
            target_context_tokens=request.target_context_tokens,
            include_evidence=request.include_evidence,
            out=request.out,
            capabilities_dir=request.capabilities_dir,
            evidence_dir=request.evidence_dir,
        ),
    )


def _health(arguments: object) -> StrictModel:
    request = HealthToolRequest.model_validate(arguments)
    return run_health_workflow(
        CapabilityHealthRequest(
            capability_name=request.capability_name,
            capabilities_dir=request.capabilities_dir,
            eval_dir=request.eval_dir,
        ),
    )


def _summary(model: StrictModel) -> dict[str, object]:
    return cast("dict[str, object]", model.model_dump(mode="json"))


TOOL_SPECS: tuple[ToolSpec, ...] = (
    ToolSpec(
        name="omf_start_session",
        description="Start a repo-local OMF agent session for the current task.",
        request_model=StartSessionToolRequest,
        handler=_start_session,
    ),
    ToolSpec(
        name="omf_record_event",
        description="Append an event to an active OMF agent session.",
        request_model=RecordEventToolRequest,
        handler=_record_event,
    ),
    ToolSpec(
        name="omf_finish_session",
        description="Mark an OMF agent session completed, failed, or unknown.",
        request_model=FinishSessionToolRequest,
        handler=_finish_session,
    ),
    ToolSpec(
        name="omf_materialize_session",
        description="Convert a finished OMF session into immutable evidence.",
        request_model=MaterializeSessionToolRequest,
        handler=_materialize_session,
    ),
    ToolSpec(
        name="omf_promote_capability",
        description="Promote materialized evidence into a capability package.",
        request_model=PromoteCapabilityToolRequest,
        handler=_promote_capability,
    ),
    ToolSpec(
        name="omf_export_capability",
        description="Export a capability package for a target agent runtime.",
        request_model=ExportCapabilityToolRequest,
        handler=_export_capability,
    ),
    ToolSpec(
        name="omf_health",
        description="Summarize capability health and the next recommended action.",
        request_model=HealthToolRequest,
        handler=_health,
    ),
)


def _tool_specs_by_name() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in TOOL_SPECS}
