import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Literal, cast

import yaml
from pydantic import Field, ValidationError

from oh_my_field.integrity import append_integrity_link, model_sha256
from oh_my_field.models import (
    CAPABILITY_NAME_PATTERN,
    CapabilityManifest,
    EvalCheck,
    EvalResult,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
    StrictModel,
)
from oh_my_field.storage import (
    DuplicateWriteError,
    StorageError,
    capability_package_paths,
    load_evidence,
    load_manifest,
    write_capability_package,
    write_eval_result,
    write_evidence,
)

type ExportTarget = Literal["codex", "claude_code", "hermes", "generic"]
type ValidationStatus = Literal["needs_validation", "needs_adaptation", "validated"]
type ToolCompatibilityStatus = Literal["pass", "partial", "unknown"]
type EvidenceInclusionMode = Literal["none", "summary", "redacted", "full"]
type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)

PORTABILITY_REQUIRED_PASS_RATE = 0.8
REDACTED_MARKER = "[REDACTED]"


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


@dataclass
class PortabilityImportNotFoundError(PortabilityError):
    capability: str
    runtime: str
    model: str | None

    def __str__(self) -> str:
        target = self.runtime if self.model is None else f"{self.runtime}/{self.model}"
        return (
            f"no imported target {target!r} for capability {self.capability!r}; "
            "run `omf capability import` first"
        )


@dataclass
class PortabilityAmbiguousTargetError(PortabilityError):
    capability: str
    runtime: str

    def __str__(self) -> str:
        return (
            f"multiple imported targets for runtime {self.runtime!r} on capability "
            f"{self.capability!r}; pass --model to disambiguate"
        )


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


class PortabilityContextBudget(StrictModel):
    source_tokens: int | None = Field(default=None, ge=1)
    target_tokens: int | None = Field(default=None, ge=1)


class PortabilityCompatibility(StrictModel):
    required_tools: tuple[str, ...] = ()
    optional_tools: tuple[str, ...] = ()
    unavailable_tools: tuple[str, ...] = ()
    context_budget: PortabilityContextBudget | None = None
    compression_required: bool = False


class PortabilityModelDelta(StrictModel):
    source_model: str | None = None
    target_model: str | None = None
    model_changed: bool = False
    transfer_type: tuple[str, ...] = ()


class PortabilityAdaptation(StrictModel):
    transfer_type: tuple[str, ...] = ()
    prompt_variant: str = "base"
    context_variant: str = "full"
    harness_required: bool = True
    human_review_required: bool = True


class PortabilityValidation(StrictModel):
    eval_set: str | None = None
    required_pass_rate: float = Field(
        default=PORTABILITY_REQUIRED_PASS_RATE,
        ge=0.0,
        le=1.0,
    )
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


class EvidenceProof(StrictModel):
    evidence_id: str = Field(min_length=1)
    available: bool
    sha256: str | None = None
    integrity_verified: bool = False
    summary_path: str | None = None
    snapshot_path: str | None = None


class EvidenceProvenancePack(StrictModel):
    mode: EvidenceInclusionMode
    proofs: tuple[EvidenceProof, ...] = ()


class EvidenceIntegrityProof(StrictModel):
    evidence_id: str = Field(min_length=1)
    available: bool
    sha256: str | None = None
    integrity_verified: bool = False


class ProvenanceIntegrity(StrictModel):
    capability: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capability_sha256: str | None = None
    capability_integrity_verified: bool = False
    evidence: tuple[EvidenceIntegrityProof, ...] = ()


class TargetValidationReport(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source: PortabilitySource
    target: PortabilityTarget
    tool_compatibility: ToolCompatibilityStatus
    unavailable_tools: tuple[str, ...] = ()
    context_remap_required: bool = False
    eval_set: str | None = None
    initial_pass_rate: float | None = Field(default=None, ge=0.0, le=1.0)
    portability_score: float = Field(ge=0.0, le=1.0)
    model_delta: PortabilityModelDelta
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None
    compact_instruction_path: str | None = None
    compressed_context_path: str | None = None
    status: ValidationStatus
    next_action: str = Field(min_length=1)


class TargetOverrides(StrictModel):
    instruction_variant: str = "base"
    context_variant: str = "full"
    required_human_review: bool = True


class TargetOverlay(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    source: PortabilitySource
    target: PortabilityTarget
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_score: float = Field(ge=0.0, le=1.0)
    transfer_type: tuple[str, ...] = ()
    overrides: TargetOverrides = Field(default_factory=TargetOverrides)
    validation_report_path: str = "validation_report.yaml"
    instructions_path: str = "instructions.md"
    context_pack_path: str = "context.pack.md"
    eval_id: str | None = None
    failure_evidence_id: str | None = None


class CapabilityPortabilityExportRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: ExportTarget
    out: Path
    capabilities_dir: Path
    target_model: str | None = None
    target_project: str | None = None
    source_project: str | None = None
    source_reasoning_effort: str | None = None
    source_context_tokens: int | None = Field(default=None, ge=1)
    target_context_tokens: int | None = Field(default=None, ge=1)
    evidence_dir: Path = Path(".omf/evidence")
    include_evidence: EvidenceInclusionMode = "summary"


class CapabilityPortabilityExportSummary(StrictModel):
    capability_name: str
    export_path: str
    portability_path: str
    runtime_export_path: str
    target_runtime: ExportTarget
    target_model: str | None = None
    evidence_mode: EvidenceInclusionMode = "summary"
    evidence_proof_count: int = Field(default=0, ge=0)


class CapabilityExportRecord(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    target: PortabilityTarget
    transfer_type: tuple[str, ...] = ()
    bundle_path: str = Field(min_length=1)
    evidence_mode: EvidenceInclusionMode = "summary"
    evidence_proof_count: int = Field(default=0, ge=0)


class CapabilityPortabilityImportRequest(StrictModel):
    bundle_path: Path
    capabilities_dir: Path
    eval_dir: Path
    evidence_dir: Path
    runtime: ExportTarget | None = None
    model: str | None = None
    project: str | None = None
    validate_import: bool = False
    available_tools: tuple[str, ...] = ()


class CapabilityPortabilityImportSummary(StrictModel):
    capability_name: str
    imported_package_path: str
    validation_report_path: str
    overlay_path: str
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_score: float = Field(ge=0.0, le=1.0)
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None


class CapabilityValidationRequest(StrictModel):
    capability_name: str = Field(pattern=CAPABILITY_NAME_PATTERN)
    capabilities_dir: Path
    eval_dir: Path
    evidence_dir: Path
    target: ExportTarget
    model: str | None = None
    project: str | None = None
    available_tools: tuple[str, ...] = ()


class CapabilityValidationSummary(StrictModel):
    capability_name: str
    overlay_path: str
    validation_report_path: str
    status: ValidationStatus
    tool_compatibility: ToolCompatibilityStatus
    portability_score: float = Field(ge=0.0, le=1.0)
    eval_id: str | None = None
    eval_path: str | None = None
    failure_evidence_id: str | None = None
    failure_evidence_path: str | None = None


def export_capability_package(
    request: CapabilityPortabilityExportRequest,
) -> CapabilityPortabilityExportSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    _ensure_new_directory(request.out)
    portability = _portability_manifest(manifest, request)
    records = _load_source_evidence(
        evidence_ids=portability.source.evidence_ids,
        evidence_dir=request.evidence_dir,
    )
    _write_export_bundle(request.out, manifest, portability)
    pack = _write_evidence_provenance(
        bundle_path=request.out,
        mode=request.include_evidence,
        manifest=manifest,
        records=records,
    )
    runtime_path = _write_runtime_target(request.out, manifest, portability)
    _write_export_record(
        capabilities_dir=request.capabilities_dir,
        record=CapabilityExportRecord(
            capability_name=manifest.name,
            target=portability.target,
            transfer_type=portability.adaptation.transfer_type,
            bundle_path=str(request.out),
            evidence_mode=request.include_evidence,
            evidence_proof_count=len(pack.proofs),
        ),
    )
    return CapabilityPortabilityExportSummary(
        capability_name=manifest.name,
        export_path=str(request.out),
        portability_path=str(request.out / "portability.yaml"),
        runtime_export_path=str(runtime_path),
        target_runtime=request.target,
        target_model=request.target_model,
        evidence_mode=request.include_evidence,
        evidence_proof_count=len(pack.proofs),
    )


def _write_export_record(
    *,
    capabilities_dir: Path,
    record: CapabilityExportRecord,
) -> Path:
    record_path = (
        capabilities_dir
        / record.capability_name
        / "exports"
        / _target_slug(record.target)
        / "export.yaml"
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(_yaml_dump(record), encoding="utf-8")
    return record_path


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
    resolved = portability.model_copy(update={"target": target})
    imported_path = write_capability_package(
        manifest,
        request.capabilities_dir,
    ).package_dir
    report = _validation_report(
        manifest=manifest,
        portability=resolved,
        available_tools=request.available_tools,
    )
    if request.validate_import:
        eval_result, eval_path = _write_target_eval(
            report=report,
            manifest=manifest,
            eval_dir=request.eval_dir,
        )
        report = report.model_copy(
            update={"eval_id": eval_result.id, "eval_path": str(eval_path)},
        )
        if eval_result.status == "fail":
            evidence, evidence_path = _write_failure_evidence(
                report=report,
                eval_result=eval_result,
                evidence_dir=request.evidence_dir,
            )
            report = report.model_copy(
                update={
                    "failure_evidence_id": evidence.id,
                    "failure_evidence_path": str(evidence_path),
                },
            )
    target_dir = imported_path / "imports" / _target_slug(report.target)
    report_path = target_dir / "validation_report.yaml"
    overlay_path = _write_target_overlay(
        target_dir=target_dir,
        report=report,
        portability=resolved,
        manifest=manifest,
    )
    _write_text_exclusive(report_path, _yaml_dump(report))
    return CapabilityPortabilityImportSummary(
        capability_name=manifest.name,
        imported_package_path=str(imported_path),
        validation_report_path=str(report_path),
        overlay_path=str(overlay_path),
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_score=report.portability_score,
        eval_id=report.eval_id,
        eval_path=report.eval_path,
        failure_evidence_id=report.failure_evidence_id,
        failure_evidence_path=report.failure_evidence_path,
    )


def validate_capability_package(
    request: CapabilityValidationRequest,
) -> CapabilityValidationSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    package_dir = capability_package_paths(
        request.capability_name,
        request.capabilities_dir,
    ).package_dir
    overlay = _find_overlay(package_dir, runtime=request.target, model=request.model)
    target = overlay.target.model_copy(
        update={
            "model": request.model or overlay.target.model,
            "project": request.project or overlay.target.project,
        },
    )
    portability = _portability_from_overlay(manifest, overlay, target)
    report = _validation_report(
        manifest=manifest,
        portability=portability,
        available_tools=request.available_tools,
    )
    eval_result, eval_path = _write_target_eval(
        report=report,
        manifest=manifest,
        eval_dir=request.eval_dir,
    )
    final_status = _validated_status(report=report, eval_result=eval_result)
    report = report.model_copy(
        update={
            "status": final_status,
            "next_action": _next_action(final_status),
            "eval_id": eval_result.id,
            "eval_path": str(eval_path),
        },
    )
    if eval_result.status == "fail":
        evidence, evidence_path = _write_failure_evidence(
            report=report,
            eval_result=eval_result,
            evidence_dir=request.evidence_dir,
        )
        report = report.model_copy(
            update={
                "failure_evidence_id": evidence.id,
                "failure_evidence_path": str(evidence_path),
            },
        )
    target_dir = package_dir / "imports" / _target_slug(target)
    report_path = target_dir / "validation_report.yaml"
    _write_text(report_path, _yaml_dump(report), overwrite=True)
    overlay_path = _write_target_overlay(
        target_dir=target_dir,
        report=report,
        portability=portability,
        manifest=manifest,
        overwrite=True,
    )
    return CapabilityValidationSummary(
        capability_name=manifest.name,
        overlay_path=str(overlay_path),
        validation_report_path=str(report_path),
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_score=report.portability_score,
        eval_id=report.eval_id,
        eval_path=report.eval_path,
        failure_evidence_id=report.failure_evidence_id,
        failure_evidence_path=report.failure_evidence_path,
    )


def _find_overlay(
    package_dir: Path,
    *,
    runtime: ExportTarget,
    model: str | None,
) -> TargetOverlay:
    matches: list[TargetOverlay] = []
    for overlay_path in sorted(package_dir.glob("imports/*/target.overlay.yaml")):
        overlay = _load_overlay(overlay_path)
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


def _load_overlay(overlay_path: Path) -> TargetOverlay | None:
    try:
        data = yaml.safe_load(overlay_path.read_text(encoding="utf-8"))
    except (OSError, yaml.YAMLError):
        return None
    try:
        return TargetOverlay.model_validate(data)
    except ValidationError:
        return None


def _portability_from_overlay(
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


def _validated_status(
    *,
    report: TargetValidationReport,
    eval_result: EvalResult,
) -> ValidationStatus:
    if (
        report.unavailable_tools
        or report.portability_score < PORTABILITY_REQUIRED_PASS_RATE
    ):
        return "needs_adaptation"
    if eval_result.status == "pass":
        return "validated"
    return "needs_validation"


def _write_target_overlay(
    *,
    target_dir: Path,
    report: TargetValidationReport,
    portability: PortabilityManifest,
    manifest: CapabilityManifest,
    overwrite: bool = False,
) -> Path:
    overlay = _build_overlay(report, portability)
    overlay_path = target_dir / "target.overlay.yaml"
    _write_text(overlay_path, _yaml_dump(overlay), overwrite=overwrite)
    _write_text(target_dir / "README.md", _target_readme(overlay), overwrite=overwrite)
    compact = overlay.overrides.instruction_variant == "compact"
    _write_text(
        target_dir / "instructions.md",
        _compact_instructions(manifest) if compact else _base_instructions(manifest),
        overwrite=overwrite,
    )
    _write_text(
        target_dir / "context.pack.md",
        _target_context_pack(
            manifest,
            portability,
            compressed=overlay.overrides.context_variant == "compressed",
        ),
        overwrite=overwrite,
    )
    return overlay_path


def _build_overlay(
    report: TargetValidationReport,
    portability: PortabilityManifest,
) -> TargetOverlay:
    return TargetOverlay(
        capability_name=report.capability_name,
        source=report.source,
        target=report.target,
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_score=report.portability_score,
        transfer_type=portability.adaptation.transfer_type,
        overrides=TargetOverrides(
            instruction_variant="compact" if _model_downgrade(portability) else "base",
            context_variant=(
                "compressed"
                if portability.compatibility.compression_required
                else "full"
            ),
            required_human_review=portability.adaptation.human_review_required,
        ),
        eval_id=report.eval_id,
        failure_evidence_id=report.failure_evidence_id,
    )


def _target_readme(overlay: TargetOverlay) -> str:
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
            f"- Portability score: {overlay.portability_score:.2f}",
            "",
            "## Adaptation",
            f"- Instruction variant: {overlay.overrides.instruction_variant}",
            f"- Context variant: {overlay.overrides.context_variant}",
            f"- Human review required: {overlay.overrides.required_human_review}",
            "",
            "## Next Action",
            f"- {_next_action(overlay.status)}",
            "",
        ],
    )


def _target_context_pack(
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
    *,
    compressed: bool,
) -> str:
    if compressed:
        return _compressed_context_pack(manifest, portability)
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
    context_budget = PortabilityContextBudget(
        source_tokens=request.source_context_tokens,
        target_tokens=request.target_context_tokens,
    )
    compression_required = _compression_required(context_budget)
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
            context_budget=context_budget,
            compression_required=compression_required,
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


def _compression_required(context_budget: PortabilityContextBudget) -> bool:
    return (
        context_budget.source_tokens is not None
        and context_budget.target_tokens is not None
        and context_budget.target_tokens < context_budget.source_tokens
    )


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
    if _model_downgrade(portability):
        _write_text_exclusive(
            bundle_path / "instructions" / "compact.md",
            _compact_instructions(manifest),
        )
        _write_text_exclusive(
            bundle_path / "instructions" / _model_notes_file(portability),
            _model_notes(portability),
        )
    _write_text_exclusive(
        bundle_path / "context" / "context.policy.yaml",
        _yaml_dump(manifest.context),
    )
    if portability.compatibility.compression_required:
        _write_text_exclusive(
            bundle_path / "context" / "context.pack.md",
            _compressed_context_pack(manifest, portability),
        )
        _write_text_exclusive(
            bundle_path / "context" / "forbidden.yaml",
            yaml.safe_dump(
                {"forbidden": list(manifest.context.forbidden)},
                sort_keys=False,
            ),
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


def _load_source_evidence(
    *,
    evidence_ids: tuple[str, ...],
    evidence_dir: Path,
) -> tuple[tuple[str, EvidenceRecord | None], ...]:
    records: list[tuple[str, EvidenceRecord | None]] = []
    for evidence_id in evidence_ids:
        try:
            records.append((evidence_id, load_evidence(evidence_id, evidence_dir)))
        except StorageError:
            records.append((evidence_id, None))
    return tuple(records)


def _write_evidence_provenance(
    *,
    bundle_path: Path,
    mode: EvidenceInclusionMode,
    manifest: CapabilityManifest,
    records: tuple[tuple[str, EvidenceRecord | None], ...],
) -> EvidenceProvenancePack:
    _write_text_exclusive(
        bundle_path / "provenance" / "integrity.yaml",
        _yaml_dump(_provenance_integrity(manifest, records)),
    )
    if mode == "none":
        return EvidenceProvenancePack(mode=mode)
    proofs: list[EvidenceProof] = []
    for evidence_id, record in records:
        summary_path: str | None = None
        snapshot_path: str | None = None
        if record is not None:
            summary_path = f"source_evidence_summaries/{evidence_id}.md"
            _write_text_exclusive(
                bundle_path / "provenance" / summary_path,
                _evidence_summary_markdown(evidence_id, record),
            )
            if mode in ("redacted", "full"):
                snapshot_path = f"source_evidence/{evidence_id}.json"
                _write_text_exclusive(
                    bundle_path / "provenance" / snapshot_path,
                    _evidence_snapshot(record, redacted=mode == "redacted"),
                )
        proofs.append(
            EvidenceProof(
                evidence_id=evidence_id,
                available=record is not None,
                sha256=_evidence_sha(record),
                integrity_verified=_evidence_integrity_ok(record),
                summary_path=summary_path,
                snapshot_path=snapshot_path,
            ),
        )
    pack = EvidenceProvenancePack(mode=mode, proofs=tuple(proofs))
    _write_text_exclusive(
        bundle_path / "provenance" / "evidence_proofs.yaml",
        _yaml_dump(pack),
    )
    if mode == "redacted":
        _write_text_exclusive(
            bundle_path / "provenance" / "redactions.yaml",
            _redactions_yaml(),
        )
    return pack


def _provenance_integrity(
    manifest: CapabilityManifest,
    records: tuple[tuple[str, EvidenceRecord | None], ...],
) -> ProvenanceIntegrity:
    capability_sha = (
        manifest.integrity_chain[-1].sha256 if manifest.integrity_chain else None
    )
    capability_verified = bool(manifest.integrity_chain) and (
        model_sha256(manifest) == manifest.integrity_chain[-1].sha256
    )
    return ProvenanceIntegrity(
        capability=manifest.name,
        capability_sha256=capability_sha,
        capability_integrity_verified=capability_verified,
        evidence=tuple(
            EvidenceIntegrityProof(
                evidence_id=evidence_id,
                available=record is not None,
                sha256=_evidence_sha(record),
                integrity_verified=_evidence_integrity_ok(record),
            )
            for evidence_id, record in records
        ),
    )


def _evidence_sha(record: EvidenceRecord | None) -> str | None:
    if record is None:
        return None
    if record.integrity_chain:
        return record.integrity_chain[-1].sha256
    return model_sha256(record)


def _evidence_integrity_ok(record: EvidenceRecord | None) -> bool:
    if record is None or not record.integrity_chain:
        return False
    return model_sha256(record) == record.integrity_chain[-1].sha256


def _evidence_summary_markdown(evidence_id: str, record: EvidenceRecord) -> str:
    runtime = f"{record.runtime.name}/{record.runtime.model or 'model_unknown'}"
    return "\n".join(
        [
            f"# Evidence {evidence_id}",
            "",
            f"- Goal: {record.goal}",
            f"- Normalized goal: {record.normalized_goal or 'not recorded'}",
            f"- Field: {record.field}",
            f"- Runtime: {runtime}",
            f"- Harness: {record.harness.status}",
            f"- Result: {record.success_or_failure_label}",
            f"- Files captured: {len(record.files)}",
            f"- Commands executed: {len(record.command_executions)}",
            f"- Errors: {len(record.errors)}",
            f"- Integrity head: {_evidence_sha(record) or 'not recorded'}",
            "",
        ],
    )


def _evidence_snapshot(record: EvidenceRecord, *, redacted: bool) -> str:
    data = cast("dict[str, YamlValue]", record.model_dump(mode="json"))
    if redacted:
        data = _redact_evidence(data)
    return json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _redact_evidence(data: dict[str, YamlValue]) -> dict[str, YamlValue]:
    _redact_list_fields(data.get("files"), ("content",))
    _redact_list_fields(data.get("command_executions"), ("stdout", "stderr"))
    _redact_list_fields(data.get("tool_calls"), ("input", "output"))
    outputs = data.get("execution_outputs")
    if isinstance(outputs, list):
        data["execution_outputs"] = [REDACTED_MARKER for _ in outputs]
    return data


def _redact_list_fields(value: YamlValue, keys: tuple[str, ...]) -> None:
    if not isinstance(value, list):
        return
    for entry in value:
        if isinstance(entry, dict):
            for key in keys:
                if entry.get(key):
                    entry[key] = REDACTED_MARKER


def _redactions_yaml() -> str:
    return yaml.safe_dump(
        {
            "mode": "redacted",
            "redacted_paths": [
                "files[].content",
                "command_executions[].stdout",
                "command_executions[].stderr",
                "execution_outputs[]",
                "tool_calls[].input",
                "tool_calls[].output",
            ],
            "note": (
                "Content fields are removed; evidence ids, hashes, and metadata "
                "are retained for offline lineage verification."
            ),
        },
        sort_keys=False,
        allow_unicode=True,
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
    portability_score = _portability_score(
        portability=portability,
        unavailable_tools=unavailable_tools,
    )
    status: ValidationStatus = (
        "needs_adaptation"
        if unavailable_tools
        or portability_score < portability.validation.required_pass_rate
        else "needs_validation"
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
        portability_score=portability_score,
        model_delta=_model_delta(portability),
        compact_instruction_path=(
            "instructions/compact.md" if _model_downgrade(portability) else None
        ),
        compressed_context_path=(
            "context/context.pack.md"
            if portability.compatibility.compression_required
            else None
        ),
        status=status,
        next_action=_next_action(status),
    )


def _write_target_eval(
    *,
    report: TargetValidationReport,
    manifest: CapabilityManifest,
    eval_dir: Path,
) -> tuple[EvalResult, Path]:
    created_at = datetime.now(UTC)
    checks = (
        EvalCheck(
            name="tool_compatibility",
            status="pass" if report.tool_compatibility != "partial" else "fail",
            message=f"tool compatibility: {report.tool_compatibility}",
        ),
        EvalCheck(
            name="context_remap",
            status="fail" if report.context_remap_required else "pass",
            message=(
                "context remap required"
                if report.context_remap_required
                else "context remap not required"
            ),
        ),
        EvalCheck(
            name="portability_score",
            status=(
                "pass"
                if report.portability_score >= PORTABILITY_REQUIRED_PASS_RATE
                else "fail"
            ),
            message=f"portability score {report.portability_score:.2f}",
        ),
    )
    failures = tuple(check.message for check in checks if check.status == "fail")
    result = EvalResult(
        id=_new_id(created_at),
        created_at=created_at,
        capability_name=manifest.name,
        source_evidence_id=manifest.source_evidence_id,
        runtime_profile=_runtime_profile(report.target),
        eval_set_name=report.eval_set,
        status="fail" if failures else "pass",
        checks=checks,
        failures=failures,
    )
    result = append_integrity_link(result, artifact_type="eval", artifact_id=result.id)
    return result, write_eval_result(result, eval_dir)


def _write_failure_evidence(
    *,
    report: TargetValidationReport,
    eval_result: EvalResult,
    evidence_dir: Path,
) -> tuple[EvidenceRecord, Path]:
    created_at = datetime.now(UTC)
    evidence = EvidenceRecord(
        id=_new_id(created_at),
        created_at=created_at,
        capability_id=report.capability_name,
        goal=f"portability validation for {report.capability_name}",
        normalized_goal=f"validate target portability for {report.capability_name}",
        field=report.target.project or "target_project",
        runtime=RuntimeInfo(name=report.target.runtime, model=report.target.model),
        errors=eval_result.failures,
        feedback=(
            f"portability score {report.portability_score:.2f}",
            f"target eval {eval_result.id} failed",
        ),
        harness=HarnessResult(
            status="fail",
            checks=tuple(check.name for check in eval_result.checks),
            failures=eval_result.failures,
            required_checks=("tool_compatibility", "portability_score"),
            human_review_required=True,
        ),
        success_or_failure_label="failure",
        improvement_notes=(
            "adapt target runtime tools, context mapping, or compact instructions",
        ),
    )
    evidence = append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )
    return evidence, write_evidence(evidence, evidence_dir)


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


def _portability_score(
    *,
    portability: PortabilityManifest,
    unavailable_tools: tuple[str, ...],
) -> float:
    score = 1.0
    if portability.source.runtime != portability.target.runtime:
        score -= 0.1
    if portability.source.model != portability.target.model:
        score -= 0.15
    if portability.source.project != portability.target.project:
        score -= 0.1
    if portability.compatibility.compression_required:
        score -= 0.1
    score -= min(0.4, 0.2 * len(unavailable_tools))
    return max(0.0, round(score, 2))


def _model_delta(portability: PortabilityManifest) -> PortabilityModelDelta:
    return PortabilityModelDelta(
        source_model=portability.source.model,
        target_model=portability.target.model,
        model_changed=portability.source.model != portability.target.model,
        transfer_type=portability.adaptation.transfer_type,
    )


def _model_downgrade(portability: PortabilityManifest) -> bool:
    if portability.source.model is None or portability.target.model is None:
        return False
    if portability.source.model == portability.target.model:
        return False
    target = portability.target.model.casefold()
    downgrade_markers = ("mini", "small", "local", "qwen", "27b", "7b")
    return any(marker in target for marker in downgrade_markers)


def _context_remap_required(portability: PortabilityManifest) -> bool:
    return (
        portability.target.project is not None
        and portability.target.project != portability.source.project
    )


def _next_action(status: ValidationStatus) -> str:
    if status == "needs_adaptation":
        return "review unavailable tools and adapt the target package"
    if status == "validated":
        return "target import validated; monitor or promote the capability"
    return "run the target eval set before marking the import validated"


def _target_slug(target: PortabilityTarget) -> str:
    model = target.model.replace("/", "_") if target.model else "model_unspecified"
    return f"{target.runtime}-{model}"


def _runtime_profile(target: PortabilityTarget) -> str:
    if target.model is None:
        return target.runtime
    return f"{target.runtime}:{target.model}"


def _new_id(created_at: datetime) -> str:
    return f"{created_at:%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


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


def _compact_instructions(manifest: CapabilityManifest) -> str:
    required_context = ", ".join(manifest.context.required) or "the required context"
    required_checks = ", ".join(manifest.harness.required_checks) or "the harness"
    return "\n".join(
        [
            f"# {manifest.name} compact",
            "",
            manifest.description,
            "",
            "## Compact Procedure",
            f"- Use only {required_context} unless the harness fails.",
            "- Prefer direct steps and avoid exploratory branching.",
            f"- Verify with {required_checks} before accepting the result.",
            "- Escalate to human review when target tools or context are missing.",
            "",
        ],
    )


def _model_notes_file(portability: PortabilityManifest) -> str:
    target_model = (portability.target.model or "model").replace("/", "_")
    return f"model_notes.{target_model}.md"


def _model_notes(portability: PortabilityManifest) -> str:
    return "\n".join(
        [
            "# Model Transfer Notes",
            "",
            f"- Source model: {portability.source.model or 'not recorded'}",
            f"- Target model: {portability.target.model or 'not recorded'}",
            f"- Transfer type: {', '.join(portability.adaptation.transfer_type)}",
            "- Use compact instructions before expanding optional context.",
            "- Run target eval before treating the import as validated.",
            "",
        ],
    )


def _compressed_context_pack(
    manifest: CapabilityManifest,
    portability: PortabilityManifest,
) -> str:
    required = "\n".join(f"- {item}" for item in manifest.context.required)
    optional = "\n".join(f"- {item}" for item in manifest.context.optional)
    budget = portability.compatibility.context_budget
    source_tokens = None if budget is None else budget.source_tokens
    target_tokens = None if budget is None else budget.target_tokens
    return "\n".join(
        [
            "# Compressed Context Pack",
            "",
            f"- Source token budget: {source_tokens or 'not recorded'}",
            f"- Target token budget: {target_tokens or 'not recorded'}",
            "- Include required context first.",
            "- Drop optional context when the target budget is smaller.",
            "",
            "## Required",
            required or "- No required context recorded.",
            "",
            "## Optional",
            optional or "- No optional context recorded.",
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
    _write_text(target_path, content, overwrite=False)


def _write_text(target_path: Path, content: str, *, overwrite: bool) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists() and not overwrite:
        raise DuplicateWriteError(path=target_path)
    target_path.write_text(content, encoding="utf-8")
