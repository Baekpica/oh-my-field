from datetime import UTC, datetime
from pathlib import Path

import pytest

from oh_my_field.models import (
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    RuntimeInfo,
)
from oh_my_field.storage import (
    DuplicateWriteError,
    EvidenceParseError,
    load_evidence,
    write_evidence,
)


def make_evidence_record() -> EvidenceRecord:
    return EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model=None),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="0" * 64,
            ),
        ),
        feedback=(),
        harness=HarnessResult(status="pass", checks=("schema_valid",), failures=()),
    )


def test_write_evidence_persists_json_and_refuses_duplicate(tmp_path: Path) -> None:
    record = make_evidence_record()

    evidence_path = write_evidence(record, tmp_path)
    loaded = load_evidence(record.id, tmp_path)

    assert evidence_path == tmp_path / f"{record.id}.json"
    assert loaded == record
    with pytest.raises(DuplicateWriteError):
        write_evidence(record, tmp_path)


def test_load_evidence_rejects_corrupt_json(tmp_path: Path) -> None:
    evidence_path = tmp_path / "bad.json"
    evidence_path.write_text("{", encoding="utf-8")

    with pytest.raises(EvidenceParseError):
        load_evidence("bad", tmp_path)
