from oh_my_field.application.portability.manifest_builder import (
    portability_from_overlay,
)
from oh_my_field.domain.portability.models import (
    CapabilityAdaptRequest,
    CapabilityAdaptSummary,
    TargetOverrides,
)
from oh_my_field.infrastructure.fs.storage import (
    capability_package_paths,
    load_manifest,
)
from oh_my_field.infrastructure.portability.overlay_store import (
    find_overlay,
    write_target_overlay,
)
from oh_my_field.infrastructure.portability.paths import target_slug


def adapt_capability_package(
    request: CapabilityAdaptRequest,
) -> CapabilityAdaptSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    package_dir = capability_package_paths(
        request.capability_name,
        request.capabilities_dir,
    ).package_dir
    overlay = find_overlay(package_dir, runtime=request.target, model=request.model)
    portability = portability_from_overlay(manifest, overlay, overlay.target)
    review_required = (
        overlay.overrides.required_human_review
        if request.require_human_review is None
        else request.require_human_review
    )
    overrides = TargetOverrides(
        instruction_variant=(
            request.instruction_variant or overlay.overrides.instruction_variant
        ),
        context_variant=request.context_variant or overlay.overrides.context_variant,
        required_human_review=review_required,
    )
    new_overlay = overlay.model_copy(update={"overrides": overrides})
    target_dir = package_dir / "imports" / target_slug(overlay.target)
    overlay_path = write_target_overlay(
        target_dir=target_dir,
        overlay=new_overlay,
        portability=portability,
        manifest=manifest,
        overwrite=True,
    )
    return CapabilityAdaptSummary(
        capability_name=manifest.name,
        overlay_path=str(overlay_path),
        instruction_variant=overrides.instruction_variant,
        context_variant=overrides.context_variant,
        required_human_review=overrides.required_human_review,
    )
