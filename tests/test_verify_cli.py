from datetime import UTC, datetime
from pathlib import Path

from typer.testing import CliRunner

from oh_my_field.cli import app
from oh_my_field.integrity import append_integrity_link
from oh_my_field.models import (
    CapturedTextFile,
    EvidenceRecord,
    HarnessResult,
    IntegrityVerificationResult,
    RuntimeInfo,
)
from oh_my_field.storage import write_evidence


def make_evidence_record() -> EvidenceRecord:
    evidence = EvidenceRecord(
        id="20260602T010203Z-deadbeef",
        created_at=datetime(2026, 6, 2, 1, 2, 3, tzinfo=UTC),
        goal="triage repo issue",
        field="local",
        runtime=RuntimeInfo(name="codex", model="gpt-5.5"),
        files=(
            CapturedTextFile(
                role="prompt",
                path="prompt.md",
                content="Find the bug.",
                size_bytes=13,
                sha256="0" * 64,
            ),
        ),
        harness=HarnessResult(status="pass", checks=("schema_valid",)),
    )
    return append_integrity_link(
        evidence,
        artifact_type="evidence",
        artifact_id=evidence.id,
    )


def test_verify_capability_integrity_chain_passes(tmp_path: Path) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    write_evidence(evidence, evidence_dir)
    promote_result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert promote_result.exit_code == 0
    verify_result = CliRunner().invoke(
        app,
        [
            "verify",
            "capability",
            "repo_issue_triage",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert verify_result.exit_code == 0
    output = IntegrityVerificationResult.model_validate_json(verify_result.stdout)
    assert output.status == "pass"
    assert {check.artifact_type for check in output.checks} == {
        "capability",
        "evidence",
    }


def test_verify_capability_detects_tampered_source_evidence(
    tmp_path: Path,
) -> None:
    evidence_dir = tmp_path / "evidence"
    capabilities_dir = tmp_path / "capabilities"
    evidence = make_evidence_record()
    evidence_path = write_evidence(evidence, evidence_dir)
    promote_result = CliRunner().invoke(
        app,
        [
            "promote",
            evidence.id,
            "--name",
            "repo_issue_triage",
            "--description",
            "GitHub issue triage capability",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )
    evidence_path.write_text(
        evidence_path.read_text(encoding="utf-8").replace(
            "triage repo issue",
            "tampered repo issue",
        ),
        encoding="utf-8",
    )

    assert promote_result.exit_code == 0
    verify_result = CliRunner().invoke(
        app,
        [
            "verify",
            "capability",
            "repo_issue_triage",
            "--evidence-dir",
            str(evidence_dir),
            "--capabilities-dir",
            str(capabilities_dir),
        ],
    )

    assert verify_result.exit_code == 1
    output = IntegrityVerificationResult.model_validate_json(verify_result.stdout)
    assert output.status == "fail"
    assert any(
        check.artifact_type == "evidence"
        and check.message == "source evidence hash does not match capability link"
        for check in output.checks
    )
