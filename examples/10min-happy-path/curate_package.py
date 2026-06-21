# ruff: noqa: INP001
"""Overlay the reviewed csv_normalize package onto a promoted package."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path
from typing import Any, cast

import yaml

from oh_my_field.domain.models import CapabilityManifest, EvidenceRecord
from oh_my_field.integrity import model_sha256


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, type=Path)
    parser.add_argument("--target", required=True, type=Path)
    parser.add_argument("--evidence", required=True, type=Path)
    args = parser.parse_args()

    evidence_id, evidence_sha = _evidence_identity(args.evidence)
    _copy_curated_package(args.source, args.target)
    _rebind_manifest(args.target / "capability.yaml", evidence_id, evidence_sha)
    return 0


def _evidence_identity(path: Path) -> tuple[str, str]:
    record = EvidenceRecord.model_validate(yaml.safe_load(path.read_text("utf-8")))
    if record.integrity_chain:
        return record.id, record.integrity_chain[-1].sha256
    return record.id, model_sha256(record)


def _copy_curated_package(source: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for filename in ("capability.yaml", "harness.yaml", "instructions.md"):
        shutil.copy2(source / filename, target / filename)
    for dirname in ("contracts", "validators"):
        destination = target / dirname
        if destination.exists():
            shutil.rmtree(destination)
        shutil.copytree(source / dirname, destination)


def _rebind_manifest(path: Path, evidence_id: str, evidence_sha: str) -> None:
    data = yaml.safe_load(path.read_text("utf-8"))
    if not isinstance(data, dict):
        message = "invalid manifest"
        raise TypeError(message)
    manifest_data = cast("dict[str, Any]", data)

    manifest_data["source_evidence_id"] = evidence_id
    manifest_data["source_evidence_ids"] = [evidence_id]
    _replace_evidence_sources(manifest_data.get("field"), evidence_id)
    _replace_evidence_sources(manifest_data.get("context"), evidence_id)

    evidence_link = {
        "artifact_type": "evidence",
        "artifact_id": evidence_id,
        "sha256": evidence_sha,
        "previous_sha256": None,
    }
    manifest_data["integrity_chain"] = [
        evidence_link,
        {
            "artifact_type": "capability",
            "artifact_id": manifest_data["name"],
            "sha256": "0" * 64,
            "previous_sha256": evidence_sha,
        },
    ]
    manifest = CapabilityManifest.model_validate(manifest_data)
    manifest_data["integrity_chain"][1]["sha256"] = model_sha256(manifest)
    CapabilityManifest.model_validate(manifest_data)
    path.write_text(
        yaml.safe_dump(manifest_data, sort_keys=False, allow_unicode=True),
        encoding="utf-8",
    )


def _replace_evidence_sources(section: object, evidence_id: str) -> None:
    if not isinstance(section, dict):
        return
    sources = section.get("sources")
    if not isinstance(sources, list):
        return
    for source in sources:
        if isinstance(source, dict) and source.get("type") == "evidence":
            source["location"] = evidence_id


if __name__ == "__main__":
    raise SystemExit(main())
