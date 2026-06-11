from pathlib import Path

from oh_my_field.domain.models import CapabilityManifest
from oh_my_field.domain.portability.models import (
    AgentView,
    CapabilityPortabilityExportRequest,
    PortabilityAdaptation,
    PortabilityCompatibility,
    PortabilityContextBudget,
    PortabilityManifest,
    PortabilitySource,
    PortabilityTarget,
    PortabilityValidation,
    TargetOverlay,
)
from oh_my_field.domain.portability.readiness import compression_required, transfer_type


def portability_from_overlay(
    manifest: CapabilityManifest,
    overlay: TargetOverlay,
    target: PortabilityTarget,
) -> PortabilityManifest:
    required_tools = manifest.workflow_control.allowed_tools or manifest.runtime.tools
    optional_tools = tuple(
        tool for tool in manifest.runtime.tools if tool not in required_tools
    )
    compressed = overlay.overrides.context_variant == "compressed"
    return PortabilityManifest(
        capability=manifest.name,
        version=manifest.version,
        source=overlay.source,
        target=target,
        agent_view=AgentView(
            skill_style="full" if overlay.direct_execution_allowed else "launcher",
            direct_execution_allowed=overlay.direct_execution_allowed,
        ),
        compatibility=PortabilityCompatibility(
            required_tools=required_tools,
            optional_tools=optional_tools,
            compression_required=compressed,
        ),
        adaptation=PortabilityAdaptation(
            transfer_type=overlay.transfer_type,
            prompt_variant=overlay.overrides.instruction_variant,
            context_variant=overlay.overrides.context_variant,
            human_review_required=overlay.overrides.required_human_review,
        ),
        validation=PortabilityValidation(eval_set=f"{manifest.name}_regression"),
    )


def build_portability_manifest(
    manifest: CapabilityManifest,
    request: CapabilityPortabilityExportRequest,
) -> PortabilityManifest:
    source_project = request.source_project or Path.cwd().name
    target_project = request.target_project or source_project
    required_tools = manifest.workflow_control.allowed_tools or manifest.runtime.tools
    optional_tools = tuple(
        tool for tool in manifest.runtime.tools if tool not in required_tools
    )
    context_budget = PortabilityContextBudget(
        source_tokens=request.source_context_tokens,
        target_tokens=request.target_context_tokens,
    )
    requires_compression = compression_required(context_budget)
    source = PortabilitySource(
        runtime=manifest.runtime.name,
        model=manifest.runtime.model,
        reasoning_effort=request.source_reasoning_effort,
        project=source_project,
        evidence_ids=manifest.source_evidence_ids or (manifest.source_evidence_id,),
    )
    target = PortabilityTarget(
        runtime=request.target,
        model=request.target_model,
        project=target_project,
    )
    return PortabilityManifest(
        capability=manifest.name,
        version=manifest.version,
        source=source,
        target=target,
        agent_view=AgentView(
            skill_style=request.skill_style,
            direct_execution_allowed=request.skill_style == "full",
        ),
        compatibility=PortabilityCompatibility(
            required_tools=required_tools,
            optional_tools=optional_tools,
            context_budget=context_budget,
            compression_required=requires_compression,
        ),
        adaptation=PortabilityAdaptation(
            transfer_type=transfer_type(source=source, target=target),
        ),
        validation=PortabilityValidation(
            eval_set=f"{manifest.name}_regression",
            status="needs_validation",
        ),
    )
