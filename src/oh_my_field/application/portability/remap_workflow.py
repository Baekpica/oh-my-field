from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.domain.portability.lifecycle import (
    target_flags,
    validate_command_hint,
)
from oh_my_field.domain.portability.models import (
    CapabilityRemapRequest,
    CapabilityRemapSummary,
    ContextRemapPlan,
    RemapBinding,
)
from oh_my_field.infrastructure.fs.storage import capability_package_paths
from oh_my_field.infrastructure.portability.bundle_store import write_text
from oh_my_field.infrastructure.portability.overlay_store import find_overlay
from oh_my_field.infrastructure.portability.paths import target_slug


def remap_capability_package(
    request: CapabilityRemapRequest,
) -> CapabilityRemapSummary:
    package_dir = capability_package_paths(
        request.capability_name,
        request.capabilities_dir,
    ).package_dir
    overlay = find_overlay(package_dir, runtime=request.target, model=request.model)
    target = overlay.target.model_copy(
        update={"project": request.target_project or overlay.target.project},
    )
    plan = ContextRemapPlan(
        capability_name=request.capability_name,
        target=target,
        bindings=tuple(
            RemapBinding(key=key, value=value) for key, value in request.mappings
        ),
        unresolved=request.unresolved,
    )
    target_dir = package_dir / "imports" / target_slug(target)
    remap_path = target_dir / "context.remap.yaml"
    write_text(remap_path, yaml_dump(plan), overwrite=True)
    if plan.unresolved:
        next_action = (
            "resolve unresolved bindings ("
            + ", ".join(plan.unresolved)
            + f") then rerun omf capability remap {request.capability_name}"
        )
    else:
        next_action = validate_command_hint(
            request.capability_name,
            target,
            target_flags(target),
        )
    return CapabilityRemapSummary(
        capability_name=request.capability_name,
        remap_path=str(remap_path),
        binding_count=len(plan.bindings),
        unresolved=plan.unresolved,
        complete=not plan.unresolved,
        next_action=next_action,
    )
