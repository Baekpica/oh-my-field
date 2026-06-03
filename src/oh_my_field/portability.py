from dataclasses import dataclass
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import Field

from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    CapabilityManifest,
    StrictModel,
)
from oh_my_field.storage import (
    DuplicateWriteError,
    load_manifest,
    write_capability_package,
)

type ExportTarget = Literal["codex", "claude_code", "hermes", "generic"]
type ValidationStatus = Literal["needs_validation", "needs_adaptation"]
type ToolCompatibilityStatus = Literal["pass", "partial", "unknown"]
type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)


class PortabilityError(Exception):
    pass


@dataclass
class PortabilityBundleExistsError(PortabilityError):
    path: Path

    def __str__(self) -> str:
        return f"refusing to overwrite existing portability bundle: {self.path}"


@dataclass
class PortabilityBundleParseError(PortabilityError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse portability bundle {self.path}: {self.reason}"


class PortabilitySource(StrictModel):
    runtime: str = Field(min_length=1)
    model: str | None = None
    reasoning_effort: str | None = None
    project: str = Field(min_length=1)
    evidence_ids: tuple[str, ...] = ()


class PortabilityTarget(StrictModel):
    runtime: ExportTarget
    model: str | None = None
    project: str | None = None


class PortabilityCompatibility(StrictModel):
    required_tools: tuple[str, ...] = ()
    optional_tools: tuple[str, ...] = ()
    unavailable_tools: tuple[str, ...] = ()
    compression_required: bool = False


class PortabilityAdaptation(StrictModel):
    transfer_type: tuple[str, ...] = ()
    prompt_variant: str = "base"
    context_variant: str = "full"
    harness_required: bool = True
    human_review_required: bool = True


class PortabilityValidation(StrictModel):
    eval_set: str | None = None
    required_pass_rate: float = Field(default=0.8, ge=0.0, le=1.0)
    current_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ValidationStatus = "needs_validation"


class PortabilityManifest(StrictModel):
    capability: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    version: str = Field(min_length=1)
    source: PortabilitySource
    target: PortabilityTarget
    compatibility: PortabilityCompatibility = Field(
        default_factory=PortabilityCompatibility,
    )
    adaptation: PortabilityAdaptation = Field(default_factory=PortabilityAdaptation)
    validation: PortabilityValidation = Field(default_factory=PortabilityValidation)


class TargetValidationReport(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source: PortabilitySource
    target: PortabilityTarget
    tool_compatibility: ToolCompatibilityStatus
    unavailable_tools: tuple[str, ...] = ()
    context_remap_required: bool = False
    eval_set: str | None = None
    initial_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    status: ValidationStatus
    next_action: str = Field(min_length=1)


class CapabilityPortabilityExportRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    out: Path
    capabilities_dir: Path
    target_model: str | None = None
    target_project: str | None = None
    source_project: str | None = None
    source_reasoning_effort: str | None = None


class CapabilityPortabilityExportSummary(StrictModel):
    capability_name: str
    export_path: str
    portability_path: str
    runtime_export_path: str
    target_runtime: ExportTarget
    target_model: str | None = None


class CapabilityPortabilityImportRequest(StrictModel):
    bundle_path: Path
    capabilities_dir: Path
    runtime: ExportTarget | None = None
    model: str | None = None
    project: str | None = None
    validate_import: bool = False
    available_tools: tuple[str, ...] = ()


class CapabilityPortabilityImportSummary(StrictModel):
    capability_name: str
    imported_package_path: str
    validation_report_path: str
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus


def export_capability_package(
    request: CapabilityPortabilityExportRequest,
) -> CapabilityPortabilityExportSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    _ensure_new_directory(request.out)
    portability = _portability_manifest(manifest, request)
    _write_export_bundle(request.out, manifest, portability)
    runtime_path = _write_runtime_target(request.out, manifest, portability)
    return CapabilityPortabilityExportSummary(
        capability_name=manifest.name,
        export_path=str(request.out),
        portability_path=str(request.out / "portability.yaml"),
        runtime_export_path=str(runtime_path),
        target_runtime=request.target,
        target_model=request.target_model,
    )


def import_capability_package(
    request: CapabilityPortabilityImportRequest,
) -> CapabilityPortabilityImportSummary:
    manifest, portability = _load_bundle(request.bundle_path)
    target = portability.target.model_copy(
        update={
            "runtime": request.runtime or portability.target.runtime,
            "model": request.model or portability.target.model,
            "project": request.project or portability.target.project,
        },
    )
    imported_path = write_capability_package(
        manifest,
        request.capabilities_dir,
    ).package_dir
    report = _validation_report(
        manifest=manifest,
        portability=portability.model_copy(update={"target": target}),
        available_tools=request.available_tools,
    )
    report_path = (
        imported_path
        / "imports"
        / _target_slug(report.target)
        / "validation_report.yaml"
    )
    _write_text_exclusive(report_path, _yaml_dump(report))
    return CapabilityPortabilityImportSummary(
        capability_name=manifest.name,
        imported_package_path=str(imported_path),
        validation_report_path=str(report_path),
        status=report.status,
        tool_compatibility=report.tool_compatibility,
    )


def _ensure_new_directory(path: Path) -> None:
    if path.exists():
        raise PortabilityBundleExistsError(path=path)
    path.mkdir(parents=True)


def _portability_manifest(
    manifest: CapabilityManifest,
    request: CapabilityPortabilityExportRequest,
) -> PortabilityManifest:
    source_project = request.source_project or Path.cwd().name
    target_project = request.target_project or source_project
    required_tools = manifest.workflow_control.allowed_tools or manifest.runtime.tools
    optional_tools = tuple(
        tool for tool in manifest.runtime.tools if tool not in required_tools
    )
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
        compatibility=PortabilityCompatibility(
            required_tools=required_tools,
            optional_tools=optional_tools,
            compression_required=False,
        ),
        adaptation=PortabilityAdaptation(
            transfer_type=_transfer_type(source=source, target=target),
        ),
        validation=PortabilityValidation(
            eval_set=f"{manifest.name}_regression",
            status="needs_validation",
        ),
    )


def _transfer_type(
    *,
    source: PortabilitySource,
    target: PortabilityTarget,
) -> tuple[str, ...]:
    values: list[str] = []
    if source.runtime != target.runtime:
        values.append("cross_runtime")
    if source.model != target.model:
        values.append("model_transfer")
    if source.project != target.project:
        values.append("project_transfer")
    return tuple(values or ("same_environment",))


def _write_export_bundle(
    bundle_path: Path,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> None:
    _write_text_exclusive(bundle_path / "capability.yaml", _yaml_dump(manifest))
    _write_text_exclusive(bundle_path / "portability.yaml", _yaml_dump(portability))
    _write_text_exclusive(bundle_path / "README.md", _bundle_readme(portability))
    _write_text_exclusive(
        bundle_path / "instructions" / "base.md",
        _base_instructions(manifest),
    )
    _write_text_exclusive(
        bundle_path / "context" / "context.policy.yaml",
        _yaml_dump(manifest.context),
    )
    _write_text_exclusive(
        bundle_path / "harness" / "harness.yaml",
        _yaml_dump(manifest.harness),
    )
    _write_text_exclusive(
        bundle_path / "provenance" / "source_runtime.yaml",
        _yaml_dump(portability.source),
    )
    _write_text_exclusive(
        bundle_path / "provenance" / "evidence_links.yaml",
        yaml.safe_dump(
            {"evidence_ids": list(portability.source.evidence_ids)},
            sort_keys=False,
        ),
    )


def _write_runtime_target(
    bundle_path: Path,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> Path:
    runtime_path = bundle_path / "runtime" / portability.target.runtime
    if portability.target.runtime == "codex":
        _write_text_exclusive(runtime_path / "AGENTS.md", _runtime_memory(manifest))
        _write_text_exclusive(
            runtime_path / "capability.md",
            _base_instructions(manifest),
        )
        _write_text_exclusive(runtime_path / "harness.md", _harness_markdown(manifest))
        _write_text_exclusive(
            runtime_path / "context.policy.md",
            _context_markdown(manifest),
        )
    elif portability.target.runtime == "claude_code":
        _write_text_exclusive(runtime_path / "CLAUDE.md", _claude_memory(manifest))
        _write_text_exclusive(
            runtime_path / "capability.md",
            _base_instructions(manifest),
        )
        _write_text_exclusive(
            runtime_path / "examples.md",
            _examples_markdown(manifest),
        )
        _write_text_exclusive(runtime_path / "checks.md", _harness_markdown(manifest))
    elif portability.target.runtime == "hermes":
        _write_text_exclusive(runtime_path / "SOUL.md", _runtime_memory(manifest))
        _write_text_exclusive(
            runtime_path / "skills" / f"{manifest.name}.md",
            _base_instructions(manifest),
        )
        _write_text_exclusive(runtime_path / "harness.md", _harness_markdown(manifest))
        _write_text_exclusive(
            runtime_path / "profile.patch.yaml",
            yaml.safe_dump(
                {
                    "skills": [f"skills/{manifest.name}.md"],
                    "harness": "harness.md",
                },
                sort_keys=False,
            ),
        )
    else:
        _write_text_exclusive(runtime_path / "skill.md", _base_instructions(manifest))
        _write_text_exclusive(
            runtime_path / "context.policy.yaml",
            _yaml_dump(manifest.context),
        )
        _write_text_exclusive(
            runtime_path / "harness.yaml",
            _yaml_dump(manifest.harness),
        )
        _write_text_exclusive(
            runtime_path / "eval_set.yaml",
            yaml.safe_dump(
                {
                    "name": f"{manifest.name}_regression",
                    "capability_name": manifest.name,
                    "cases": [],
                },
                sort_keys=False,
            ),
        )
    return runtime_path


def _load_bundle(bundle_path: Path) -> tuple[CapabilityManifest, PortabilityManifest]:
    try:
        capability_yaml = bundle_path.joinpath("capability.yaml").read_text(
            encoding="utf-8",
        )
        portability_yaml = bundle_path.joinpath("portability.yaml").read_text(
            encoding="utf-8",
        )
    except OSError as exc:
        raise PortabilityBundleParseError(path=bundle_path, reason=str(exc)) from exc
    try:
        capability_data = yaml.safe_load(capability_yaml)
        portability_data = yaml.safe_load(portability_yaml)
        manifest = CapabilityManifest.model_validate(capability_data)
        portability = PortabilityManifest.model_validate(portability_data)
    except (yaml.YAMLError, ValueError) as exc:
        raise PortabilityBundleParseError(path=bundle_path, reason=str(exc)) from exc
    return manifest, portability


def _validation_report(
    *,
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
    available_tools: tuple[str, ...],
) -> TargetValidationReport:
    unavailable_tools = _unavailable_tools(
        required_tools=portability.compatibility.required_tools,
        available_tools=available_tools,
    )
    tool_compatibility = _tool_compatibility(
        available_tools=available_tools,
        unavailable_tools=unavailable_tools,
    )
    status: ValidationStatus = (
        "needs_adaptation" if unavailable_tools else "needs_validation"
    )
    return TargetValidationReport(
        capability_name=manifest.name,
        source=portability.source,
        target=portability.target,
        tool_compatibility=tool_compatibility,
        unavailable_tools=unavailable_tools,
        context_remap_required=_context_remap_required(portability),
        eval_set=portability.validation.eval_set,
        initial_pass_rate=portability.validation.current_pass_rate,
        status=status,
        next_action=_next_action(status),
    )


def _unavailable_tools(
    *,
    required_tools: tuple[str, ...],
    available_tools: tuple[str, ...],
) -> tuple[str, ...]:
    if not available_tools:
        return ()
    available = set(available_tools)
    return tuple(tool for tool in required_tools if tool not in available)


def _tool_compatibility(
    *,
    available_tools: tuple[str, ...],
    unavailable_tools: tuple[str, ...],
) -> ToolCompatibilityStatus:
    if not available_tools:
        return "unknown"
    if unavailable_tools:
        return "partial"
    return "pass"


def _context_remap_required(portability: PortabilityManifest) -> bool:
    return (
        portability.target.project is not None
        and portability.target.project != portability.source.project
    )


def _next_action(status: ValidationStatus) -> str:
    if status == "needs_adaptation":
        return "review unavailable tools and adapt the target package"
    return "run the target eval set before marking the import validated"


def _target_slug(target: PortabilityTarget) -> str:
    model = target.model.replace("/", "_") if target.model else "model_unspecified"
    return f"{target.runtime}-{model}"


def _bundle_readme(portability: PortabilityManifest) -> str:
    return "\n".join(
        [
            f"# {portability.capability}",
            "",
            "## Portability",
            f"- Source: {portability.source.runtime}/{portability.source.model}",
            f"- Target: {portability.target.runtime}/{portability.target.model}",
            f"- Transfer: {', '.join(portability.adaptation.transfer_type)}",
            "",
        ],
    )


def _base_instructions(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            manifest.description,
            "",
            "## Use",
            f"- Goal: {manifest.normalized_goal}",
            "- Apply the context policy before acting.",
            "- Run the harness before accepting the result.",
            "- Record target-specific failures as new evidence.",
            "",
        ],
    )


def _runtime_memory(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "Use this imported OMF capability package as guidance for this project.",
            "Do not treat OMF as the agent runtime; use the local agent normally.",
            "",
            "## Capability",
            manifest.description,
            "",
        ],
    )


def _claude_memory(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            f"# {manifest.name}",
            "",
            "Project memory for an imported OMF capability package.",
            "Use this guidance when the current task matches the capability.",
            "",
            "## Instructions",
            "- Read capability.md before acting.",
            "- Follow checks.md before marking the result complete.",
            "- Preserve target-specific failures as OMF evidence.",
            "",
            "## Capability",
            manifest.description,
            "",
        ],
    )


def _examples_markdown(manifest: CapabilityManifest) -> str:
    return "\n".join(
        [
            "# Examples",
            "",
            "## Success",
            f"- A target run satisfies `{manifest.normalized_goal}` and passes checks.",
            "",
            "## Failure",
            "- Missing context, unavailable tools, or failed checks require evidence.",
            "",
        ],
    )


def _harness_markdown(manifest: CapabilityManifest) -> str:
    checks = "\n".join(f"- {check}" for check in manifest.harness.required_checks)
    return f"# Harness\n\n{checks or '- No required checks recorded.'}\n"


def _context_markdown(manifest: CapabilityManifest) -> str:
    required = "\n".join(f"- {item}" for item in manifest.context.required)
    forbidden = "\n".join(f"- {item}" for item in manifest.context.forbidden)
    return (
        "# Context Policy\n\n"
        "## Required\n"
        f"{required or '- No required context recorded.'}\n\n"
        "## Forbidden\n"
        f"{forbidden or '- No forbidden context recorded.'}\n"
    )


def _yaml_dump(model: StrictModel) -> str:
    data = cast("dict[str, YamlValue]", model.model_dump(mode="json"))
    yaml_text: str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
    return yaml_text


def _write_text_exclusive(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise DuplicateWriteError(path=target_path)
    target_path.write_text(content, encoding="utf-8")
