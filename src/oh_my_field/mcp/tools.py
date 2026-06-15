from collections.abc import Callable
from dataclasses import dataclass
from typing import cast

from oh_my_field.application.explain_artifacts import ExplainRequest, explain_artifact
from oh_my_field.application.health import (
    CapabilityHealthRequest,
    run_card_workflow,
    run_health_workflow,
)
from oh_my_field.application.portability import (
    adapt_capability_package,
    export_capability_package,
    import_capability_package,
    remap_capability_package,
    validate_capability_package,
)
from oh_my_field.application.promote import PromoteRequest, run_promote_workflow
from oh_my_field.application.registry import RegistryRequest, run_registry_workflow
from oh_my_field.application.session import (
    finish_session,
    materialize_session,
    record_session_event,
    start_session,
)
from oh_my_field.domain.models import StrictModel
from oh_my_field.domain.portability.models import (
    CapabilityAdaptRequest,
    CapabilityPortabilityExportRequest,
    CapabilityPortabilityImportRequest,
    CapabilityRemapRequest,
    CapabilityValidationRequest,
)
from oh_my_field.mcp.schemas import (
    AdaptCapabilityToolRequest,
    CapabilityInspectToolSummary,
    CardToolRequest,
    ExplainToolRequest,
    ExportCapabilityToolRequest,
    FinishSessionToolRequest,
    HealthToolRequest,
    ImportCapabilityToolRequest,
    InspectCapabilityToolRequest,
    ListCapabilitiesToolRequest,
    MaterializeSessionToolRequest,
    McpToolDefinition,
    PromoteCapabilityToolRequest,
    RecordArtifactToolRequest,
    RecordDecisionToolRequest,
    RecordEventToolRequest,
    RecordInputToolRequest,
    RecordValidationToolRequest,
    RemapCapabilityToolRequest,
    StartSessionToolRequest,
    ValidateCapabilityToolRequest,
)
from oh_my_field.storage import load_manifest

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


def _record_input(arguments: object) -> StrictModel:
    request = RecordInputToolRequest.model_validate(arguments)
    return record_session_event(
        session_id=request.session_id,
        event_type="context",
        summary=request.summary,
        path=request.path,
        sessions_dir=request.sessions_dir,
    )


def _record_artifact(arguments: object) -> StrictModel:
    request = RecordArtifactToolRequest.model_validate(arguments)
    return record_session_event(
        session_id=request.session_id,
        event_type="artifact",
        summary=request.summary,
        path=request.path,
        sessions_dir=request.sessions_dir,
    )


def _record_validation(arguments: object) -> StrictModel:
    request = RecordValidationToolRequest.model_validate(arguments)
    return record_session_event(
        session_id=request.session_id,
        event_type="test_result",
        summary=request.summary,
        path=request.artifact_path,
        command=request.command,
        exit_code=request.exit_code,
        sessions_dir=request.sessions_dir,
    )


def _record_decision(arguments: object) -> StrictModel:
    request = RecordDecisionToolRequest.model_validate(arguments)
    return record_session_event(
        session_id=request.session_id,
        event_type="decision",
        summary=request.summary,
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
            strict=request.strict,
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
            skill_style=request.skill_style,
            bundle_format=request.bundle_format,
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


def _list_capabilities(arguments: object) -> StrictModel:
    request = ListCapabilitiesToolRequest.model_validate(arguments)
    return run_registry_workflow(
        RegistryRequest(
            capability_name=request.capability_name,
            capabilities_dir=request.capabilities_dir,
            eval_dir=request.eval_dir,
        ),
    )


def _inspect_capability(arguments: object) -> StrictModel:
    request = InspectCapabilityToolRequest.model_validate(arguments)
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    return CapabilityInspectToolSummary(
        capability_name=manifest.name,
        version=manifest.version,
        description=manifest.description,
        status=manifest.status,
        normalized_goal=manifest.normalized_goal,
        runtime_name=manifest.runtime.name,
        runtime_model=manifest.runtime.model,
        runtime_tools=manifest.runtime.tools,
        required_context=manifest.context.required,
        forbidden_context=manifest.context.forbidden,
        required_checks=manifest.harness.required_checks,
        source_evidence_ids=manifest.source_evidence_ids
        or (manifest.source_evidence_id,),
    )


def _validate_capability(arguments: object) -> StrictModel:
    request = ValidateCapabilityToolRequest.model_validate(arguments)
    return validate_capability_package(
        CapabilityValidationRequest(
            capability_name=request.capability_name,
            capabilities_dir=request.capabilities_dir,
            eval_dir=request.eval_dir,
            evidence_dir=request.evidence_dir,
            target=request.target,
            model=request.model,
            project=request.project,
            available_tools=request.available_tools,
            run_command=request.run_command,
            run_argv=request.run_argv,
            expected_artifacts=request.expected_artifacts,
            command_cwd=request.command_cwd,
            command_timeout_seconds=request.command_timeout_seconds,
            run_contract_validator=request.run_contract_validator,
            require_cwd_inside_project=request.require_cwd_inside_project,
            # approve_command_risk / allow_env deliberately omitted: the MCP
            # surface must not let a prompt-controlled client self-approve risky
            # commands or restore stripped secret env vars. These default to the
            # safe record-don't-execute behavior in CapabilityValidationRequest.
        ),
    )


def _import_capability(arguments: object) -> StrictModel:
    request = ImportCapabilityToolRequest.model_validate(arguments)
    return import_capability_package(
        CapabilityPortabilityImportRequest(
            bundle_path=request.bundle_path,
            import_dir=request.import_dir,
            capabilities_dir=request.capabilities_dir,
            eval_dir=request.eval_dir,
            evidence_dir=request.evidence_dir,
            runtime=request.runtime,
            model=request.model,
            project=request.project,
            validate_import=request.validate_import,
            available_tools=request.available_tools,
            as_name=request.as_name,
            namespace=request.namespace,
            if_exists=request.if_exists,
        ),
    )


def _remap_capability(arguments: object) -> StrictModel:
    request = RemapCapabilityToolRequest.model_validate(arguments)
    return remap_capability_package(
        CapabilityRemapRequest(
            capability_name=request.capability_name,
            capabilities_dir=request.capabilities_dir,
            target=request.target,
            model=request.model,
            target_project=request.target_project,
            mappings=tuple(request.mappings.items()),
            unresolved=request.unresolved,
        ),
    )


def _adapt_capability(arguments: object) -> StrictModel:
    request = AdaptCapabilityToolRequest.model_validate(arguments)
    return adapt_capability_package(
        CapabilityAdaptRequest(
            capability_name=request.capability_name,
            capabilities_dir=request.capabilities_dir,
            target=request.target,
            model=request.model,
            instruction_variant=request.instruction_variant,
            context_variant=request.context_variant,
            require_human_review=request.require_human_review,
        ),
    )


def _explain(arguments: object) -> StrictModel:
    request = ExplainToolRequest.model_validate(arguments)
    return explain_artifact(
        ExplainRequest(
            target_type=request.target_type,
            target_id=request.target_id,
            rule=request.rule,
            check=request.check,
            capabilities_dir=request.capabilities_dir,
            learning_patch_dir=request.learning_patch_dir,
        ),
    )


def _card(arguments: object) -> StrictModel:
    request = CardToolRequest.model_validate(arguments)
    return run_card_workflow(
        capability_name=request.capability_name,
        capabilities_dir=request.capabilities_dir,
        write=request.write,
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
        description=(
            "Append a generic event to an active OMF agent session. "
            "Prefer omf_record_input/artifact/validation/decision for "
            "portable capability evidence."
        ),
        request_model=RecordEventToolRequest,
        handler=_record_event,
    ),
    ToolSpec(
        name="omf_record_input",
        description="Record required input context for a strict portable capability.",
        request_model=RecordInputToolRequest,
        handler=_record_input,
    ),
    ToolSpec(
        name="omf_record_artifact",
        description="Record a produced artifact path for contract snapshotting.",
        request_model=RecordArtifactToolRequest,
        handler=_record_artifact,
    ),
    ToolSpec(
        name="omf_record_validation",
        description="Record a validation result, command, and optional artifact path.",
        request_model=RecordValidationToolRequest,
        handler=_record_validation,
    ),
    ToolSpec(
        name="omf_record_decision",
        description="Record a reusable-workflow or portability decision.",
        request_model=RecordDecisionToolRequest,
        handler=_record_decision,
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
    ToolSpec(
        name="omf_list_capabilities",
        description="List capabilities in the local OMF registry with health status.",
        request_model=ListCapabilitiesToolRequest,
        handler=_list_capabilities,
    ),
    ToolSpec(
        name="omf_inspect_capability",
        description=(
            "Inspect a capability's goal, context policy, harness checks, and "
            "runtime assumptions instead of reading them from skill files."
        ),
        request_model=InspectCapabilityToolRequest,
        handler=_inspect_capability,
    ),
    ToolSpec(
        name="omf_validate_capability",
        description=(
            "Re-validate an imported capability against a target runtime. "
            "Pass run_command (your runtime's run invocation) to observe a real "
            "target run and reach the terminal `validated` status; without it "
            "the target stays `needs_validation` (pending, not a failure)."
        ),
        request_model=ValidateCapabilityToolRequest,
        handler=_validate_capability,
    ),
    ToolSpec(
        name="omf_import_capability",
        description=(
            "Import a portable capability bundle into the local registry and "
            "write a target validation report."
        ),
        request_model=ImportCapabilityToolRequest,
        handler=_import_capability,
    ),
    ToolSpec(
        name="omf_remap_capability",
        description=(
            "Record a context remap plan binding source context keys to target "
            "values for an imported target."
        ),
        request_model=RemapCapabilityToolRequest,
        handler=_remap_capability,
    ),
    ToolSpec(
        name="omf_adapt_capability",
        description=(
            "Apply instruction/context/review overrides to an imported target "
            "to resolve a needs_adaptation status."
        ),
        request_model=AdaptCapabilityToolRequest,
        handler=_adapt_capability,
    ),
    ToolSpec(
        name="omf_explain",
        description=(
            "Explain why an OMF capability, harness, or learning patch is in its "
            "current state instead of guessing from raw files."
        ),
        request_model=ExplainToolRequest,
        handler=_explain,
    ),
    ToolSpec(
        name="omf_card",
        description="Render the human capability card (goal, contract, portability).",
        request_model=CardToolRequest,
        handler=_card,
    ),
)


def _tool_specs_by_name() -> dict[str, ToolSpec]:
    return {spec.name: spec for spec in TOOL_SPECS}
