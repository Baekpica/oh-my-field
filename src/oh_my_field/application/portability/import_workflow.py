from pathlib import Path

from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.application.portability.validation_support import (
    build_overlay,
    pass_rate_comparison,
    validation_report,
    write_failure_evidence,
    write_target_eval,
)
from oh_my_field.domain.models import CapabilityManifest
from oh_my_field.domain.portability.errors import PortabilityImportExistsError
from oh_my_field.domain.portability.models import (
    CapabilityPortabilityImportRequest,
    CapabilityPortabilityImportSummary,
    ImportCollisionPolicy,
)
from oh_my_field.infrastructure.fs.storage import (
    capability_package_paths,
    manifest_path_for_capability,
    update_manifest,
    write_capability_package,
)
from oh_my_field.infrastructure.portability.bundle_store import load_bundle, write_text
from oh_my_field.infrastructure.portability.overlay_store import write_target_overlay
from oh_my_field.infrastructure.portability.paths import target_slug


def import_capability_package(
    request: CapabilityPortabilityImportRequest,
) -> CapabilityPortabilityImportSummary:
    manifest, portability = load_bundle(request.bundle_path)
    target = portability.target.model_copy(
        update={
            "runtime": request.runtime or portability.target.runtime,
            "model": request.model or portability.target.model,
            "project": request.project or portability.target.project,
        },
    )
    resolved = portability.model_copy(update={"target": target})
    target_caps = (
        request.capabilities_dir / request.namespace
        if request.namespace
        else request.capabilities_dir
    )
    if request.as_name is not None:
        manifest = manifest.model_copy(update={"name": request.as_name})
    manifest, imported_path, overwrite_target = _materialize_package(
        manifest=manifest,
        capabilities_dir=target_caps,
        if_exists=request.if_exists,
    )
    report = validation_report(
        manifest=manifest,
        portability=resolved,
        available_tools=request.available_tools,
    )
    if request.validate_import:
        eval_result, eval_path = write_target_eval(
            report=report,
            manifest=manifest,
            eval_dir=request.eval_dir,
        )
        report = report.model_copy(
            update={
                "eval_id": eval_result.id,
                "eval_path": str(eval_path),
                "pass_rate_comparison": pass_rate_comparison(manifest, eval_result),
            },
        )
        if eval_result.status == "fail":
            evidence, evidence_path = write_failure_evidence(
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
    target_dir = imported_path / "imports" / target_slug(report.target)
    report_path = target_dir / "validation_report.yaml"
    overlay_path = write_target_overlay(
        target_dir=target_dir,
        overlay=build_overlay(report, resolved),
        portability=resolved,
        manifest=manifest,
        overwrite=overwrite_target,
    )
    write_text(report_path, yaml_dump(report), overwrite=overwrite_target)
    return CapabilityPortabilityImportSummary(
        capability_name=manifest.name,
        imported_package_path=str(imported_path),
        validation_report_path=str(report_path),
        overlay_path=str(overlay_path),
        status=report.status,
        tool_compatibility=report.tool_compatibility,
        portability_readiness_score=report.readiness.score,
        eval_id=report.eval_id,
        eval_path=report.eval_path,
        failure_evidence_id=report.failure_evidence_id,
        failure_evidence_path=report.failure_evidence_path,
    )


def _materialize_package(
    *,
    manifest: CapabilityManifest,
    capabilities_dir: Path,
    if_exists: ImportCollisionPolicy,
) -> tuple[CapabilityManifest, Path, bool]:
    exists = manifest_path_for_capability(manifest.name, capabilities_dir) is not None
    if if_exists == "version" and exists:
        manifest = manifest.model_copy(
            update={"name": _next_versioned_name(manifest.name, capabilities_dir)},
        )
        exists = False
    package_dir = capability_package_paths(
        manifest.name,
        capabilities_dir,
    ).package_dir
    if not exists:
        write_capability_package(manifest, capabilities_dir)
        return manifest, package_dir, False
    if if_exists == "fail":
        raise PortabilityImportExistsError(
            capability=manifest.name,
            capabilities_dir=capabilities_dir,
        )
    if if_exists == "overwrite":
        update_manifest(manifest, capabilities_dir)
    # "merge" keeps the existing canonical package and only rewrites the
    # target import directory below.
    return manifest, package_dir, True


def _next_versioned_name(name: str, capabilities_dir: Path) -> str:
    index = 2
    while True:
        candidate = f"{name}_v{index}"
        if manifest_path_for_capability(candidate, capabilities_dir) is None:
            return candidate
        index += 1
