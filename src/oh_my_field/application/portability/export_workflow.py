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
    ensure_new_directory,
    write_export_bundle,
)
from oh_my_field.infrastructure.portability.paths import target_slug


def export_capability_package(
    request: CapabilityPortabilityExportRequest,
) -> CapabilityPortabilityExportSummary:
    manifest = load_manifest(request.capability_name, request.capabilities_dir)
    ensure_new_directory(request.out)
    portability = build_portability_manifest(manifest, request)
    records = load_source_evidence(
        evidence_ids=portability.source.evidence_ids,
        evidence_dir=request.evidence_dir,
    )
    write_export_bundle(request.out, manifest, portability)
    pack = write_evidence_provenance(
        bundle_path=request.out,
        mode=request.include_evidence,
        manifest=manifest,
        records=records,
    )
    runtime_path = write_runtime_target(request.out, manifest, portability)
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
        / target_slug(record.target)
        / "export.yaml"
    )
    record_path.parent.mkdir(parents=True, exist_ok=True)
    record_path.write_text(yaml_dump(record), encoding="utf-8")
    return record_path
