import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from pydantic import ValidationError

from oh_my_field.models import EvidenceRecord


class StorageError(Exception):
    pass


@dataclass(frozen=True, slots=True)
class DuplicateWriteError(StorageError):
    path: Path

    def __str__(self) -> str:
        return f"refusing to overwrite existing file: {self.path}"


@dataclass(frozen=True, slots=True)
class EvidenceNotFoundError(StorageError):
    evidence_id: str
    evidence_dir: Path

    def __str__(self) -> str:
        return f"evidence {self.evidence_id!r} not found in {self.evidence_dir}"


@dataclass(frozen=True, slots=True)
class EvidenceParseError(StorageError):
    path: Path
    reason: str

    def __str__(self) -> str:
        return f"could not parse evidence file {self.path}: {self.reason}"


def write_evidence(record: EvidenceRecord, evidence_dir: Path) -> Path:
    target_path = evidence_dir / f"{record.id}.json"
    _write_text_exclusive(target_path, record.model_dump_json(indent=2) + "\n")
    return target_path


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
