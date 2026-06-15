from pathlib import Path

from oh_my_field.adapters.runtime_export import write_runtime_target
from oh_my_field.application.portability.manifest_builder import (
    build_portability_manifest,
)
from oh_my_field.application.portability.provenance import (
    load_source_evidence,
    write_evidence_provenance,
)
from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.domain.portability.models import (
    CapabilityExportRecord,
    CapabilityPortabilityExportRequest,
    CapabilityPortabilityExportSummary,
)
from oh_my_field.infrastructure.fs.storage import load_manifest
from oh_my_field.infrastructure.portability.bundle_store import (
    create_archive,
    ensure_new_directory,
    package_archive_path,
    package_staging_dir,
    write_export_bundle,
    write_package_metadata,
)
from oh_my_field.infrastructure.portability.paths import target_slug


def export_capability_package(
    request: CapabilityPortabilityExportRequest,
) -> CapabilityPortabilityExportSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    bundle_path = (
        package_staging_dir(request.out)
        if request.bundle_format == "archive"
        else request.out
    )
    package_path = (
        package_archive_path(request.out)
        if request.bundle_format == "archive"
        else request.out
    )
    ensure_new_directory(bundle_path)
    portability = build_portability_manifest(manifest, request)
    records = load_source_evidence(
        evidence_ids=portability.source.evidence_ids,
        evidence_dir=request.evidence_dir,
    )
    write_export_bundle(bundle_path, manifest, portability)
    pack = write_evidence_provenance(
        bundle_path=bundle_path,
        mode=request.include_evidence,
        manifest=manifest,
        records=records,
    )
    runtime_path = write_runtime_target(bundle_path, manifest, portability)
    write_package_metadata(bundle_path, portability)
    if request.bundle_format == "archive":
        create_archive(bundle_path, package_path)
    _write_export_record(
        capabilities_dir=request.capabilities_dir,
        record=CapabilityExportRecord(
            capability_name=manifest.name,
            target=portability.target,
            transfer_type=portability.adaptation.transfer_type,
            bundle_path=str(package_path),
            evidence_mode=request.include_evidence,
            evidence_proof_count=len(pack.proofs),
        ),
    )
    return CapabilityPortabilityExportSummary(
        capability_name=manifest.name,
        export_path=str(bundle_path),
        package_path=str(package_path),
        unpacked_path=str(bundle_path) if request.bundle_format == "archive" else None,
        portability_path=str(bundle_path / "portability.yaml"),
        runtime_export_path=str(runtime_path),
        target_runtime=request.target,
        target_model=request.target_model,
        bundle_format=request.bundle_format,
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
        / target_slug(record.target)
        / "export.yaml"
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(yaml_dump(record), encoding="utf-8")
    return record_path
