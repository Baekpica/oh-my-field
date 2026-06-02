import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import ValidationError

from oh_my_field.models import (
    CapabilityManifest,
    EvalResult,
    EvidenceRecord,
    ReplayRecord,
)

type YamlValue = (
    str | int | float | bool | None | list["YamlValue"] | dict[str, "YamlValue"]
)


class StorageError(Exception):
    pass


@dataclass
class DuplicateWriteError(StorageError):
    path: Path

    def __str__(self) -> str:
        return f"refusing to overwrite existing file: {self.path}"


@dataclass
class EvidenceNotFoundError(StorageError):
    evidence_id: str
    evidence_dir: Path

    def __str__(self) -> str:
        return f"evidence {self.evidence_id!r} not found in {self.evidence_dir}"


@dataclass
class EvidenceParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse evidence file {self.path}: {self.reason}"


@dataclass
class ManifestNotFoundError(StorageError):
    capability_name: str
    capabilities_dir: Path

    def __str__(self) -> str:
        return (
            f"manifest for capability {self.capability_name!r} not found in "
            f"{self.capabilities_dir}"
        )


@dataclass
class ManifestParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse manifest file {self.path}: {self.reason}"


@dataclass
class ReplayNotFoundError(StorageError):
    replay_id: str
    replay_dir: Path

    def __str__(self) -> str:
        return f"replay {self.replay_id!r} not found in {self.replay_dir}"


@dataclass
class ReplayParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse replay file {self.path}: {self.reason}"


def write_evidence(record: EvidenceRecord, evidence_dir: Path) -> Path:
    target_path = evidence_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def write_manifest(manifest: CapabilityManifest, capabilities_dir: Path) -> Path:
    target_path = capabilities_dir / manifest.name / "manifest.yaml"
    _write_text_exclusive(target_path, _manifest_yaml(manifest))
    return target_path


def load_manifest(capability_name: str, capabilities_dir: Path) -> CapabilityManifest:
    manifest_path = capabilities_dir / capability_name / "manifest.yaml"
    if not manifest_path.exists():
        raise ManifestNotFoundError(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
        )
    try:
        raw_yaml = manifest_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ManifestNotFoundError(
            capability_name=capability_name,
            capabilities_dir=capabilities_dir,
        ) from exc
    except UnicodeDecodeError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc
    try:
        parsed_yaml = yaml.safe_load(raw_yaml)
    except yaml.YAMLError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc
    if not isinstance(parsed_yaml, dict):
        raise ManifestParseError(
            path=manifest_path,
            reason=f"expected mapping at top level, got {type(parsed_yaml).__name__}",
        )
    try:
        return CapabilityManifest.model_validate(parsed_yaml)
    except ValidationError as exc:
        raise ManifestParseError(path=manifest_path, reason=str(exc)) from exc


def load_evidence(evidence_id: str, evidence_dir: Path) -> EvidenceRecord:
    evidence_path = evidence_dir / f"{evidence_id}.json"
    if not evidence_path.exists():
        raise EvidenceNotFoundError(evidence_id=evidence_id, evidence_dir=evidence_dir)
    try:
        raw_json = evidence_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise EvidenceNotFoundError(
            evidence_id=evidence_id,
            evidence_dir=evidence_dir,
        ) from exc
    except UnicodeDecodeError as exc:
        raise EvidenceParseError(path=evidence_path, reason=str(exc)) from exc
    try:
        return EvidenceRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        raise EvidenceParseError(path=evidence_path, reason=str(exc)) from exc


def write_replay(record: ReplayRecord, replay_dir: Path) -> Path:
    target_path = replay_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


def load_replay(replay_id: str, replay_dir: Path) -> ReplayRecord:
    replay_path = replay_dir / f"{replay_id}.json"
    if not replay_path.exists():
        raise ReplayNotFoundError(replay_id=replay_id, replay_dir=replay_dir)
    try:
        raw_json = replay_path.read_text(encoding="utf-8")
    except FileNotFoundError as exc:
        raise ReplayNotFoundError(replay_id=replay_id, replay_dir=replay_dir) from exc
    except UnicodeDecodeError as exc:
        raise ReplayParseError(path=replay_path, reason=str(exc)) from exc
    try:
        return ReplayRecord.model_validate_json(raw_json)
    except ValidationError as exc:
        raise ReplayParseError(path=replay_path, reason=str(exc)) from exc


def write_eval_result(result: EvalResult, eval_dir: Path) -> Path:
    target_path = eval_dir / f"{result.id}.json"
    _write_text_exclusive(target_path, result.model_dump_json(indent=2) + "\n")
    return target_path


def _write_text_exclusive(target_path: Path, content: str) -> None:
    target_path.parent.mkdir(parents=True, exist_ok=True)
    if target_path.exists():
        raise DuplicateWriteError(path=target_path)

    with tempfile.NamedTemporaryFile(
        "w",
        delete=False,
        dir=target_path.parent,
        encoding="utf-8",
        prefix=f".{target_path.name}.",
        suffix=".tmp",
    ) as temp_file:
        temp_path = Path(temp_file.name)
        temp_file.write(content)

    try:
        os.link(temp_path, target_path)
    except FileExistsError as exc:
        raise DuplicateWriteError(path=target_path) from exc
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _manifest_yaml(manifest: CapabilityManifest) -> str:
    yaml_text: str = yaml.safe_dump(
        _manifest_yaml_data(manifest),
        sort_keys=False,
        allow_unicode=True,
    )
    return yaml_text


def _manifest_yaml_data(manifest: CapabilityManifest) -> dict[str, YamlValue]:
    return {
        "name": manifest.name,
        "version": manifest.version,
        "description": manifest.description,
        "status": manifest.status,
        "source_evidence_id": manifest.source_evidence_id,
        "normalized_goal": manifest.normalized_goal,
        "inputs": list(manifest.inputs),
        "workflow": {
            "graph": manifest.workflow.graph,
            "nodes": list(manifest.workflow.nodes),
        },
        "harness": {
            "status": manifest.harness.status,
            "checks": list(manifest.harness.checks),
            "failures": list(manifest.harness.failures),
        },
        "runtime": {
            "name": manifest.runtime.name,
            "model": manifest.runtime.model,
        },
        "promotion_criteria": {
            "min_success_runs": manifest.promotion_criteria.min_success_runs,
            "max_human_intervention_rate": (
                manifest.promotion_criteria.max_human_intervention_rate
            ),
            "required_harness_pass_rate": (
                manifest.promotion_criteria.required_harness_pass_rate
            ),
        },
    }
