from pathlib import Path

import yaml
from pydantic import ValidationError

from oh_my_field.domain.models import CapabilityManifest
from oh_my_field.domain.portability.errors import (
    PortabilityAmbiguousTargetError,
    PortabilityImportNotFoundError,
)
from oh_my_field.domain.portability.lifecycle import next_validation_action
from oh_my_field.domain.portability.models import (
    ExportTarget,
    PortabilityManifest,
    TargetOverlay,
)
from oh_my_field.infrastructure.portability.bundle_store import write_text


def find_overlay(
    package_dir: Path,
    *,
    runtime: ExportTarget,
    model: str | None,
) -> TargetOverlay:
    matches: list[TargetOverlay] = []
    for overlay_path in sorted(package_dir.glob("imports/*/target.overlay.yaml")):
        overlay = load_overlay(overlay_path)
        if overlay is None or overlay.target.runtime != runtime:
            continue
        if model is not None and overlay.target.model != model:
            continue
        matches.append(overlay)
    if not matches:
        raise PortabilityImportNotFoundError(
            capability=package_dir.name,
            runtime=runtime,
            model=model,
        )
    if len(matches) > 1:
        raise PortabilityAmbiguousTargetError(
            capability=package_dir.name,
            runtime=runtime,
        )
    return matches[0]


def load_overlay(overlay_path: Path) -> TargetOverlay | None:
    try:
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    try:
        return TargetOverlay.model_validate(data)
    except ValidationError:
        return None


def write_target_overlay(
    *,
    target_dir: Path,
    overlay: TargetOverlay,
    portability: PortabilityManifest,
    manifest: CapabilityManifest,
    overwrite: bool = False,
) -> Path:
    from oh_my_field.application.portability.rendering import (  # noqa: PLC0415
        base_instructions,
        compact_instructions,
        yaml_dump,
    )

    overlay_path = target_dir / "target.overlay.yaml"
    write_text(overlay_path, yaml_dump(overlay), overwrite=overwrite)
    write_text(target_dir / "README.md", target_readme(overlay), overwrite=overwrite)
    compact = overlay.overrides.instruction_variant == "compact"
    write_text(
        target_dir / "instructions.md",
        compact_instructions(manifest) if compact else base_instructions(manifest),
        overwrite=overwrite,
    )
    write_text(
        target_dir / "context.pack.md",
        target_context_pack(
            manifest,
            portability,
            compressed=overlay.overrides.context_variant == "compressed",
        ),
        overwrite=overwrite,
    )
    return overlay_path


def target_readme(overlay: TargetOverlay) -> str:
    source_model = overlay.source.model or "model_unknown"
    target_model = overlay.target.model or "model_unknown"
    return "\n".join(
        [
            f"# {overlay.capability_name} ({overlay.target.runtime})",
            "",
            "## Imported Target",
            f"- Source: {overlay.source.runtime}/{source_model}",
            f"- Target: {overlay.target.runtime}/{target_model}",
            f"- Project: {overlay.target.project or 'not recorded'}",
            f"- Status: {overlay.status}",
            f"- Tool compatibility: {overlay.tool_compatibility}",
            f"- Portability readiness: {overlay.portability_readiness_score:.2f}",
            "",
            "## Adaptation",
            f"- Instruction variant: {overlay.overrides.instruction_variant}",
            f"- Context variant: {overlay.overrides.context_variant}",
            f"- Human review required: {overlay.overrides.required_human_review}",
            "",
            "## Next Action",
            f"- {next_validation_action(overlay.status)}",
            "",
        ],
    )


def target_context_pack(
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
    *,
    compressed: bool,
) -> str:
    if compressed:
        from oh_my_field.application.portability.rendering import (  # noqa: PLC0415
            compressed_context_pack,
        )

        return compressed_context_pack(manifest, portability)
    required = "\n".join(f"- {item}" for item in manifest.context.required)
    optional = "\n".join(f"- {item}" for item in manifest.context.optional)
    return "\n".join(
        [
            "# Context Pack",
            "",
            "## Required",
            required or "- No required context recorded.",
            "",
            "## Optional",
            optional or "- No optional context recorded.",
            "",
        ],
    )
