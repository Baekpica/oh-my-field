import json
from pathlib import Path
from typing import cast

import yaml

from oh_my_field.application.portability.rendering import yaml_dump
from oh_my_field.domain.models import CapabilityManifest, EvidenceRecord
from oh_my_field.domain.portability.models import (
    REDACTED_MARKER,
    EvidenceInclusionMode,
    EvidenceIntegrityProof,
    EvidenceProof,
    EvidenceProvenancePack,
    ProvenanceIntegrity,
    YamlValue,
)
from oh_my_field.infrastructure.fs.storage import StorageError, load_evidence
from oh_my_field.infrastructure.portability.bundle_store import write_text_exclusive
from oh_my_field.integrity import model_sha256


def load_source_evidence(
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


def write_evidence_provenance(
    *,
    bundle_path: Path,
    mode: EvidenceInclusionMode,
    manifest: CapabilityManifest,
    records: tuple[tuple[str, EvidenceRecord | None], ...],
) -> EvidenceProvenancePack:
    write_text_exclusive(
        bundle_path / "provenance" / "integrity.yaml",
        yaml_dump(_provenance_integrity(manifest, records)),
    )
    if mode == "none":
        return EvidenceProvenancePack(mode=mode)
    proofs: list[EvidenceProof] = []
    for evidence_id, record in records:
        summary_path: str | None = None
        snapshot_path: str | None = None
        if record is not None:
            summary_path = f"source_evidence_summaries/{evidence_id}.md"
            write_text_exclusive(
                bundle_path / "provenance" / summary_path,
                _evidence_summary_markdown(evidence_id, record),
            )
            if mode in ("redacted", "full"):
                snapshot_path = f"source_evidence/{evidence_id}.json"
                write_text_exclusive(
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
    write_text_exclusive(
        bundle_path / "provenance" / "evidence_proofs.yaml",
        yaml_dump(pack),
    )
    if mode == "redacted":
        write_text_exclusive(
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
